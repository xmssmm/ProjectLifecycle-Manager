from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.handover_requests import get_handover_request_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.handover_requests import HandoverRequest, HandoverRequestStatus
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.users import User, UserRole, UserStatus
from app.schemas.handover_requests import (
    HandoverCandidateDecision,
    HandoverCandidateReview,
    HandoverRequestCreate,
    HandoverReviewDecision,
    HandoverReviewRequest,
)
from app.services.audit import InMemoryAuditLogWriter
from app.services.handover_requests import (
    HandoverRequestDetail,
    HandoverRequestService,
    InMemoryHandoverRequestRepository,
)
from app.services.notifications import InMemoryNotificationRepository, NotificationService


def make_user(role: UserRole, *, username: str, dept_id: UUID | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=dept_id,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_main_project(*, dept_id: UUID) -> MainProject:
    now = datetime.now(UTC)
    return MainProject(
        id=uuid4(),
        project_no="Z-2026-0001",
        name="Main",
        dept_id=dept_id,
        status=MainProjectStatus.in_progress,
        total_budget=Decimal("500000.00"),
        expected_finish_date=date(2026, 12, 31),
        spent_amount=Decimal("0.00"),
        remark=None,
        creator_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_sub_project(
    main_project: MainProject,
    manager: User,
    *,
    name: str = "Sub",
) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no=f"{main_project.project_no}-ZX-{uuid4().hex[:3]}",
        name=name,
        main_project_id=main_project.id,
        dept_id=main_project.dept_id,
        budget=Decimal("100000.00"),
        manager_id=manager.id,
        creator_id=manager.id,
        status=SubProjectStatus.in_progress,
        plan_end_date=date(2026, 10, 31),
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark=None,
        created_at=now,
        updated_at=now,
    )


def make_member(
    sub_project: SubProject,
    user: User,
    role: SubProjectMemberRole,
) -> SubProjectMember:
    now = datetime.now(UTC)
    return SubProjectMember(
        id=uuid4(),
        sub_project_id=sub_project.id,
        user_id=user.id,
        role_in_project=role,
        joined_at=now,
        created_at=now,
        updated_at=now,
    )


def make_service(
    *,
    users: list[User],
    main_projects: list[MainProject],
    sub_projects: list[SubProject],
    members: list[SubProjectMember],
    now: datetime | None = None,
) -> tuple[
    HandoverRequestService,
    InMemoryHandoverRequestRepository,
    InMemoryNotificationRepository,
]:
    repository = InMemoryHandoverRequestRepository(
        main_projects=main_projects,
        sub_projects=sub_projects,
        members=members,
        users=users,
    )
    notifications = InMemoryNotificationRepository()
    service = HandoverRequestService(
        repository=repository,
        notification_service=NotificationService(repository=notifications),
        now_provider=lambda: now or datetime(2026, 5, 10, tzinfo=UTC),
    )
    return service, repository, notifications


@pytest.mark.asyncio
async def test_submit_rejects_self_candidate() -> None:
    dept_id = uuid4()
    leader = make_user(UserRole.proj_leader, username="leader", dept_id=dept_id)
    main_project = make_main_project(dept_id=dept_id)
    sub_project = make_sub_project(main_project, leader)
    service, _repository, _notifications = make_service(
        users=[leader],
        main_projects=[main_project],
        sub_projects=[sub_project],
        members=[make_member(sub_project, leader, SubProjectMemberRole.proj_leader)],
    )

    with pytest.raises(BusinessException) as exc:
        await service.submit_request(
            actor=leader,
            payload=HandoverRequestCreate(
                sub_project_ids=[sub_project.id],
                to_user_id=leader.id,
                reason="rotation",
            ),
        )

    assert exc.value.code == 3003


@pytest.mark.asyncio
async def test_candidate_confirm_before_review_does_not_change_manager() -> None:
    dept_id = uuid4()
    leader = make_user(UserRole.proj_leader, username="leader", dept_id=dept_id)
    candidate = make_user(UserRole.proj_leader, username="candidate", dept_id=dept_id)
    dept_manager = make_user(UserRole.dept_manager, username="manager", dept_id=dept_id)
    main_project = make_main_project(dept_id=dept_id)
    sub_project = make_sub_project(main_project, leader)
    service, repository, notifications = make_service(
        users=[leader, candidate, dept_manager],
        main_projects=[main_project],
        sub_projects=[sub_project],
        members=[make_member(sub_project, leader, SubProjectMemberRole.proj_leader)],
    )

    detail = await service.submit_request(
        actor=leader,
        payload=HandoverRequestCreate(
            sub_project_ids=[sub_project.id],
            to_user_id=candidate.id,
            reason="rotation",
        ),
    )
    confirmed = await service.review_candidate(
        actor=candidate,
        request_id=detail.request.id,
        payload=HandoverCandidateReview(decision=HandoverCandidateDecision.confirm),
    )

    assert sub_project.manager_id == leader.id
    assert confirmed.request.status.value == "pending_review"
    assert repository.handovers == []
    assert {item.scenario for item in notifications.notifications} >= {
        "handover_request_candidate",
        "handover_request_pending_review",
    }


@pytest.mark.asyncio
async def test_dept_manager_approval_transfers_related_sub_projects_and_writes_audit() -> None:
    dept_id = uuid4()
    leader = make_user(UserRole.proj_leader, username="leader", dept_id=dept_id)
    candidate = make_user(UserRole.proj_leader, username="candidate", dept_id=dept_id)
    dept_manager = make_user(UserRole.dept_manager, username="manager", dept_id=dept_id)
    main_project = make_main_project(dept_id=dept_id)
    project_a = make_sub_project(main_project, leader, name="A")
    project_b = make_sub_project(main_project, leader, name="B")
    service, repository, _notifications = make_service(
        users=[leader, candidate, dept_manager],
        main_projects=[main_project],
        sub_projects=[project_a, project_b],
        members=[
            make_member(project_a, leader, SubProjectMemberRole.proj_leader),
            make_member(project_b, leader, SubProjectMemberRole.proj_leader),
        ],
    )
    audit_writer = InMemoryAuditLogWriter()
    detail = await service.submit_request(
        actor=leader,
        payload=HandoverRequestCreate(
            sub_project_ids=[project_a.id, project_b.id],
            to_user_id=candidate.id,
            reason="rotation",
        ),
    )
    await service.review_candidate(
        actor=candidate,
        request_id=detail.request.id,
        payload=HandoverCandidateReview(decision=HandoverCandidateDecision.confirm),
    )

    reviewed = await service.review_request(
        actor=dept_manager,
        request_id=detail.request.id,
        payload=HandoverReviewRequest(decision=HandoverReviewDecision.approve),
        audit_writer=audit_writer,
    )

    assert reviewed.request.status.value == "approved"
    assert {project_a.manager_id, project_b.manager_id} == {candidate.id}
    assert len(repository.handovers) == 2
    assert {entry.action for entry in audit_writer.entries} == {"handover_request.review"}


@pytest.mark.asyncio
async def test_admin_can_force_after_candidate_timeout() -> None:
    dept_id = uuid4()
    leader = make_user(UserRole.proj_leader, username="leader", dept_id=dept_id)
    candidate = make_user(UserRole.proj_leader, username="candidate", dept_id=dept_id)
    admin = make_user(UserRole.admin, username="admin")
    main_project = make_main_project(dept_id=dept_id)
    sub_project = make_sub_project(main_project, leader)
    service, _repository, _notifications = make_service(
        users=[leader, candidate, admin],
        main_projects=[main_project],
        sub_projects=[sub_project],
        members=[make_member(sub_project, leader, SubProjectMemberRole.proj_leader)],
        now=datetime(2026, 5, 18, tzinfo=UTC),
    )
    detail = await service.submit_request(
        actor=leader,
        payload=HandoverRequestCreate(
            sub_project_ids=[sub_project.id],
            to_user_id=candidate.id,
            reason="rotation",
        ),
    )
    detail.request.created_at = datetime(2026, 5, 10, tzinfo=UTC)

    forced = await service.force_request(actor=admin, request_id=detail.request.id)

    assert forced.request.status.value == "forced"
    assert sub_project.manager_id == candidate.id


def test_handover_request_endpoints_return_standard_payloads() -> None:
    current_actor = make_user(UserRole.admin, username="admin")
    leader = make_user(UserRole.proj_leader, username="leader")
    candidate = make_user(UserRole.proj_leader, username="candidate")
    now = datetime.now(UTC)
    request = HandoverRequest(
        id=uuid4(),
        from_user_id=leader.id,
        to_user_id=candidate.id,
        reason="rotation",
        status=HandoverRequestStatus.pending_candidate,
        candidate_comment=None,
        candidate_responded_at=None,
        reviewer_id=None,
        review_comment=None,
        reviewed_at=None,
        forced_by_id=None,
        forced_at=None,
        created_at=now,
        updated_at=now,
    )
    sub_project_id = uuid4()
    detail = HandoverRequestDetail(request=request, sub_project_ids=[sub_project_id])

    class FakeHandoverRequestService:
        async def list_requests(
            self,
            *,
            actor: User,
            status: HandoverRequestStatus | None = None,
        ) -> list[HandoverRequestDetail]:
            assert actor.id == current_actor.id
            assert status == HandoverRequestStatus.pending_candidate
            return [detail]

        async def submit_request(
            self,
            *,
            actor: User,
            payload: HandoverRequestCreate,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> HandoverRequestDetail:
            _ = audit_writer, audit_context
            assert actor.id == current_actor.id
            assert payload.to_user_id == candidate.id
            return detail

        async def review_candidate(
            self,
            *,
            actor: User,
            request_id: UUID,
            payload: HandoverCandidateReview,
        ) -> HandoverRequestDetail:
            assert actor.id == current_actor.id
            assert request_id == request.id
            assert payload.decision == HandoverCandidateDecision.confirm
            request.status = HandoverRequestStatus.pending_review
            return detail

        async def review_request(
            self,
            *,
            actor: User,
            request_id: UUID,
            payload: HandoverReviewRequest,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> HandoverRequestDetail:
            _ = audit_writer, audit_context
            assert actor.id == current_actor.id
            assert request_id == request.id
            assert payload.decision == HandoverReviewDecision.approve
            request.status = HandoverRequestStatus.approved
            return detail

        async def force_request(
            self,
            *,
            actor: User,
            request_id: UUID,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> HandoverRequestDetail:
            _ = audit_writer, audit_context
            assert actor.id == current_actor.id
            assert request_id == request.id
            request.status = HandoverRequestStatus.forced
            return detail

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return current_actor

    async def fake_service() -> FakeHandoverRequestService:
        return FakeHandoverRequestService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_handover_request_service] = fake_service
    client = TestClient(app)

    list_response = client.get(
        "/api/v1/handover-requests",
        params={"status": "pending_candidate"},
    )
    submit_response = client.post(
        "/api/v1/handover-requests",
        json={
            "reason": "rotation",
            "sub_project_ids": [str(sub_project_id)],
            "to_user_id": str(candidate.id),
        },
    )
    candidate_response = client.post(
        f"/api/v1/handover-requests/{request.id}/candidate-review",
        json={"decision": "confirm"},
    )
    review_response = client.post(
        f"/api/v1/handover-requests/{request.id}/review",
        json={"decision": "approve"},
    )
    force_response = client.post(f"/api/v1/handover-requests/{request.id}/force")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == str(request.id)
    assert submit_response.status_code == 200
    assert submit_response.json()["data"]["to_user_id"] == str(candidate.id)
    assert candidate_response.status_code == 200
    assert candidate_response.json()["data"]["status"] == "pending_review"
    assert review_response.status_code == 200
    assert review_response.json()["data"]["status"] == "approved"
    assert force_response.status_code == 200
    assert force_response.json()["data"]["status"] == "forced"
