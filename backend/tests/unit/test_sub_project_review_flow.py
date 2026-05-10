from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import BusinessException
from app.models.main_projects import MainProject, MainProjectStatus, ProjectReviewDecision
from app.models.phases import PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.schemas.sub_projects import SubProjectReviewRequest, SubProjectTerminateRequest
from app.services.audit import AuditContext, InMemoryAuditLogWriter
from app.services.notifications import InMemoryNotificationRepository, NotificationService
from app.services.sub_projects import InMemorySubProjectRepository, SubProjectService


def make_user(role: UserRole, *, username: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_main_project(*, budget: Decimal = Decimal("100000.00")) -> MainProject:
    now = datetime.now(UTC)
    return MainProject(
        id=uuid4(),
        project_no="Z-2026-0001",
        name="主项目A",
        dept_id=uuid4(),
        status=MainProjectStatus.not_started,
        total_budget=budget,
        expected_finish_date=date(2026, 12, 31),
        spent_amount=Decimal("0.00"),
        remark=None,
        creator_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_sub_project(
    *,
    main_project: MainProject,
    creator: User,
    budget: Decimal = Decimal("30000.00"),
    status: SubProjectStatus = SubProjectStatus.pending_review,
) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no=f"{main_project.project_no}-ZX-001",
        name="子项目A",
        main_project_id=main_project.id,
        dept_id=uuid4(),
        budget=budget,
        manager_id=creator.id,
        creator_id=creator.id,
        status=status,
        plan_end_date=date(2026, 10, 31),
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark="baseline",
        created_at=now,
        updated_at=now,
    )


def make_service(
    *,
    users: list[User],
    main_projects: list[MainProject],
    sub_projects: list[SubProject],
) -> tuple[SubProjectService, InMemorySubProjectRepository, InMemoryNotificationRepository]:
    repository = InMemorySubProjectRepository(
        main_projects=main_projects,
        sub_projects=sub_projects,
        users=users,
    )
    notification_repository = InMemoryNotificationRepository()
    service = SubProjectService(
        repository=repository,
        notification_service=NotificationService(
            repository=notification_repository,
            business_date_provider=lambda: date(2026, 5, 10),
        ),
        today_provider=lambda: date(2026, 5, 10),
    )
    return service, repository, notification_repository


@pytest.mark.asyncio
async def test_submit_sub_project_notifies_dept_managers_and_records_audit() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    manager = make_user(UserRole.dept_manager, username="manager")
    main_project = make_main_project()
    sub_project = make_sub_project(
        main_project=main_project,
        creator=leader,
        status=SubProjectStatus.rejected,
    )
    service, _repository, notification_repository = make_service(
        users=[leader, manager],
        main_projects=[main_project],
        sub_projects=[sub_project],
    )
    audit_writer = InMemoryAuditLogWriter()

    submitted = await service.submit_sub_project(
        actor=leader,
        sub_project_id=sub_project.id,
        audit_writer=audit_writer,
        audit_context=AuditContext(actor_id=leader.id, request_id="req-submit-sub"),
    )

    assert submitted.status == SubProjectStatus.pending_review
    assert notification_repository.notifications[0].scenario == "project_pending_review"
    assert notification_repository.notifications[0].receiver_id == manager.id
    assert audit_writer.entries[0].action == "sub_project.submit"


@pytest.mark.asyncio
async def test_review_sub_project_approves_and_creates_six_phases() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    reviewer = make_user(UserRole.dept_manager, username="reviewer")
    main_project = make_main_project()
    sub_project = make_sub_project(main_project=main_project, creator=leader)
    service, repository, notification_repository = make_service(
        users=[leader, reviewer],
        main_projects=[main_project],
        sub_projects=[sub_project],
    )
    audit_writer = InMemoryAuditLogWriter()

    with pytest.raises(BusinessException) as self_review:
        await service.review_sub_project(
            actor=leader,
            sub_project_id=sub_project.id,
            payload=SubProjectReviewRequest(decision=ProjectReviewDecision.approve),
        )
    assert self_review.value.code == 1003

    reviewed = await service.review_sub_project(
        actor=reviewer,
        sub_project_id=sub_project.id,
        payload=SubProjectReviewRequest(decision=ProjectReviewDecision.approve),
        audit_writer=audit_writer,
        audit_context=AuditContext(actor_id=reviewer.id, request_id="req-review-sub"),
    )

    assert reviewed.status == SubProjectStatus.in_progress
    assert len(repository.phases) == 6
    assert [phase.phase_no for phase in repository.phases] == [1, 2, 3, 4, 5, 6]
    assert repository.phases[0].status == PhaseStatus.in_progress
    assert [phase.status for phase in repository.phases[1:]] == [
        PhaseStatus.waiting,
        PhaseStatus.waiting,
        PhaseStatus.waiting,
        PhaseStatus.in_progress,
        PhaseStatus.waiting,
    ]
    assert repository.reviews[0].decision == ProjectReviewDecision.approve
    assert notification_repository.notifications[0].scenario == "project_review_result"
    assert notification_repository.notifications[0].receiver_id == leader.id
    assert audit_writer.entries[0].extra["admin_override"] is False


@pytest.mark.asyncio
async def test_review_sub_project_requires_over_budget_confirmation() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    admin = make_user(UserRole.admin, username="admin")
    main_project = make_main_project(budget=Decimal("100000.00"))
    existing = make_sub_project(
        main_project=main_project,
        creator=leader,
        budget=Decimal("90000.00"),
        status=SubProjectStatus.not_started,
    )
    candidate = make_sub_project(
        main_project=main_project,
        creator=leader,
        budget=Decimal("20000.00"),
    )
    service, repository, _notification_repository = make_service(
        users=[leader, admin],
        main_projects=[main_project],
        sub_projects=[existing, candidate],
    )
    audit_writer = InMemoryAuditLogWriter()

    with pytest.raises(BusinessException) as over_budget:
        await service.review_sub_project(
            actor=admin,
            sub_project_id=candidate.id,
            payload=SubProjectReviewRequest(decision=ProjectReviewDecision.approve),
        )

    assert over_budget.value.code == 3001
    assert over_budget.value.data["over_budget_amount"] == "10000.00"

    reviewed = await service.review_sub_project(
        actor=admin,
        sub_project_id=candidate.id,
        payload=SubProjectReviewRequest(
            decision=ProjectReviewDecision.approve,
            confirm_over_budget=True,
            over_budget_reason="业务必须拆分执行",
        ),
        audit_writer=audit_writer,
    )

    assert reviewed.status == SubProjectStatus.in_progress
    assert repository.reviews[0].admin_override is True
    assert audit_writer.entries[0].extra["over_budget_warning"] is True
    assert audit_writer.entries[0].extra["over_budget_reason"] == "业务必须拆分执行"


@pytest.mark.asyncio
async def test_review_sub_project_reject_path() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    reviewer = make_user(UserRole.dept_manager, username="reviewer")
    main_project = make_main_project()
    sub_project = make_sub_project(main_project=main_project, creator=leader)
    service, repository, _notification_repository = make_service(
        users=[leader, reviewer],
        main_projects=[main_project],
        sub_projects=[sub_project],
    )

    reviewed = await service.review_sub_project(
        actor=reviewer,
        sub_project_id=sub_project.id,
        payload=SubProjectReviewRequest(
            decision=ProjectReviewDecision.reject,
            review_comment="预算说明不完整",
        ),
    )

    assert reviewed.status == SubProjectStatus.rejected
    assert repository.reviews[0].review_comment == "预算说明不完整"
    assert repository.phases == []


@pytest.mark.asyncio
async def test_close_sub_project_requires_all_six_phases_completed() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    reviewer = make_user(UserRole.dept_manager, username="reviewer")
    main_project = make_main_project()
    sub_project = make_sub_project(
        main_project=main_project,
        creator=leader,
        status=SubProjectStatus.in_progress,
    )
    service, repository, _notification_repository = make_service(
        users=[leader, reviewer],
        main_projects=[main_project],
        sub_projects=[sub_project],
    )
    service._create_default_phases(sub_project_id=sub_project.id, actor_id=reviewer.id)

    with pytest.raises(BusinessException) as blocked:
        await service.close_sub_project(actor=reviewer, sub_project_id=sub_project.id)
    assert blocked.value.code == 3003

    for phase in repository.phases:
        phase.status = PhaseStatus.completed
    sub_project.status = SubProjectStatus.completed

    audit_writer = InMemoryAuditLogWriter()
    closed = await service.close_sub_project(
        actor=reviewer,
        sub_project_id=sub_project.id,
        audit_writer=audit_writer,
    )

    assert closed.status == SubProjectStatus.closed
    assert closed.actual_end_date == date(2026, 5, 10)
    assert audit_writer.entries[0].action == "sub_project.close"
    assert audit_writer.entries[0].extra["phase_count"] == 6


@pytest.mark.asyncio
async def test_terminate_sub_project_requires_privileged_role_and_reason() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    admin = make_user(UserRole.admin, username="admin")
    main_project = make_main_project()
    sub_project = make_sub_project(
        main_project=main_project,
        creator=leader,
        status=SubProjectStatus.in_progress,
    )
    service, _repository, _notification_repository = make_service(
        users=[leader, admin],
        main_projects=[main_project],
        sub_projects=[sub_project],
    )
    audit_writer = InMemoryAuditLogWriter()

    with pytest.raises(BusinessException) as denied:
        await service.terminate_sub_project(
            actor=leader,
            sub_project_id=sub_project.id,
            payload=SubProjectTerminateRequest(reason="负责人申请中止"),
        )
    assert denied.value.code == 1003

    terminated = await service.terminate_sub_project(
        actor=admin,
        sub_project_id=sub_project.id,
        payload=SubProjectTerminateRequest(reason="采购取消"),
        audit_writer=audit_writer,
    )

    assert terminated.status == SubProjectStatus.terminated
    assert terminated.actual_end_date == date(2026, 5, 10)
    assert audit_writer.entries[0].action == "sub_project.terminate"
    assert audit_writer.entries[0].extra["reason"] == "采购取消"


def test_terminate_reason_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        SubProjectTerminateRequest(reason="   ")
