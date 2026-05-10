from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import BusinessException
from app.models.main_projects import MainProject, MainProjectStatus, ProjectReviewDecision
from app.models.users import User, UserRole, UserStatus
from app.schemas.main_projects import MainProjectReviewRequest, MainProjectReviewUpdate
from app.services.audit import AuditContext, InMemoryAuditLogWriter
from app.services.main_projects import InMemoryMainProjectRepository, MainProjectService
from app.services.notifications import InMemoryNotificationRepository, NotificationService


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


def make_project(creator: User, *, status: MainProjectStatus) -> MainProject:
    now = datetime.now(UTC)
    return MainProject(
        id=uuid4(),
        project_no="Z-2026-0001",
        name="主项目A",
        dept_id=uuid4(),
        status=status,
        total_budget=Decimal("100000.00"),
        expected_finish_date=date(2026, 12, 31),
        spent_amount=Decimal("0.00"),
        remark="baseline",
        creator_id=creator.id,
        created_at=now,
        updated_at=now,
    )


def make_service(
    *,
    users: list[User],
    projects: list[MainProject],
) -> tuple[MainProjectService, InMemoryMainProjectRepository, InMemoryNotificationRepository]:
    repository = InMemoryMainProjectRepository(projects, users=users)
    notification_repository = InMemoryNotificationRepository()
    service = MainProjectService(
        repository=repository,
        notification_service=NotificationService(
            repository=notification_repository,
            business_date_provider=lambda: date(2026, 5, 10),
        ),
        today_provider=lambda: date(2026, 5, 10),
    )
    return service, repository, notification_repository


@pytest.mark.asyncio
async def test_submit_project_notifies_other_dept_managers_and_records_audit() -> None:
    creator = make_user(UserRole.dept_manager, username="creator")
    reviewer = make_user(UserRole.dept_manager, username="reviewer")
    project = make_project(creator, status=MainProjectStatus.rejected)
    service, _repository, notification_repository = make_service(
        users=[creator, reviewer],
        projects=[project],
    )
    audit_writer = InMemoryAuditLogWriter()

    submitted = await service.submit_project(
        actor=creator,
        project_id=project.id,
        audit_writer=audit_writer,
        audit_context=AuditContext(actor_id=creator.id, request_id="req-submit"),
    )

    assert submitted.status == MainProjectStatus.pending_review
    assert len(notification_repository.notifications) == 1
    notification = notification_repository.notifications[0]
    assert notification.scenario == "project_pending_review"
    assert notification.receiver_id == reviewer.id
    assert notification.source_id == str(project.id)
    assert len(audit_writer.entries) == 1
    assert audit_writer.entries[0].action == "main_project.submit"
    assert audit_writer.entries[0].target_id == str(project.id)


@pytest.mark.asyncio
async def test_submit_project_requires_creator_and_allowed_status() -> None:
    creator = make_user(UserRole.dept_manager, username="creator")
    other = make_user(UserRole.dept_manager, username="other")
    project = make_project(creator, status=MainProjectStatus.not_started)
    service, _repository, _notification_repository = make_service(
        users=[creator, other],
        projects=[project],
    )

    with pytest.raises(BusinessException) as wrong_actor:
        await service.submit_project(actor=other, project_id=project.id)
    assert wrong_actor.value.code == 1003

    with pytest.raises(BusinessException) as wrong_status:
        await service.submit_project(actor=creator, project_id=project.id)
    assert wrong_status.value.code == 3003


@pytest.mark.asyncio
async def test_review_rejects_self_review_and_admin_records_override_diff() -> None:
    creator = make_user(UserRole.dept_manager, username="creator")
    admin = make_user(UserRole.admin, username="admin")
    project = make_project(creator, status=MainProjectStatus.pending_review)
    service, repository, notification_repository = make_service(
        users=[creator, admin],
        projects=[project],
    )
    audit_writer = InMemoryAuditLogWriter()

    with pytest.raises(BusinessException) as self_review:
        await service.review_project(
            actor=creator,
            project_id=project.id,
            payload=MainProjectReviewRequest(decision=ProjectReviewDecision.approve),
        )
    assert self_review.value.code == 1010

    reviewed = await service.review_project(
        actor=admin,
        project_id=project.id,
        payload=MainProjectReviewRequest(
            decision=ProjectReviewDecision.approve,
            updates=MainProjectReviewUpdate(name="主项目A-修订"),
            review_comment="同意",
        ),
        audit_writer=audit_writer,
        audit_context=AuditContext(actor_id=admin.id, request_id="req-review"),
    )

    assert reviewed.status == MainProjectStatus.not_started
    assert reviewed.name == "主项目A-修订"
    assert len(repository.reviews) == 1
    review = repository.reviews[0]
    assert review.decision == ProjectReviewDecision.approve
    assert review.admin_override is True
    assert review.modified_fields == {"name": {"before": "主项目A", "after": "主项目A-修订"}}
    assert len(notification_repository.notifications) == 1
    assert notification_repository.notifications[0].scenario == "project_review_result"
    assert notification_repository.notifications[0].receiver_id == creator.id
    assert len(audit_writer.entries) == 1
    assert audit_writer.entries[0].extra["admin_override"] is True
    assert audit_writer.entries[0].extra["modified_fields"] == review.modified_fields


@pytest.mark.asyncio
async def test_review_reject_path_records_comment_and_rejected_status() -> None:
    creator = make_user(UserRole.dept_manager, username="creator")
    reviewer = make_user(UserRole.dept_manager, username="reviewer")
    project = make_project(creator, status=MainProjectStatus.pending_review)
    service, repository, _notification_repository = make_service(
        users=[creator, reviewer],
        projects=[project],
    )

    reviewed = await service.review_project(
        actor=reviewer,
        project_id=project.id,
        payload=MainProjectReviewRequest(
            decision=ProjectReviewDecision.reject,
            review_comment="资料不完整",
        ),
    )

    assert reviewed.status == MainProjectStatus.rejected
    assert repository.reviews[0].decision == ProjectReviewDecision.reject
    assert repository.reviews[0].review_comment == "资料不完整"
