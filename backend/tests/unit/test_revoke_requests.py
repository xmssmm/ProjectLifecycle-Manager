from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table

from app.api.v1.revoke_requests import get_revoke_request_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.base import Base
from app.models.documents import Document
from app.models.phases import Phase, PhaseStatus
from app.models.revoke_requests import RevokeRequest, RevokeRequestStatus, RevokeReviewDecision
from app.models.sub_projects import (
    SubProject,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.tasks import Task, TaskStatus
from app.models.users import User, UserRole, UserStatus
from app.schemas.revoke_requests import (
    RevokeRequestCreate,
    RevokeRequestRead,
    RevokeRequestReview,
)
from app.services.audit import AuditContext, InMemoryAuditLogWriter
from app.services.notifications import InMemoryNotificationRepository, NotificationService
from app.services.revoke_requests import InMemoryRevokeRequestRepository, RevokeRequestService


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


def make_sub_project(manager: User) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no="Z-2026-0001-ZX-001",
        name="Procurement delivery",
        main_project_id=uuid4(),
        dept_id=uuid4(),
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


def make_phase(
    sub_project: SubProject,
    *,
    phase_no: int,
    status: PhaseStatus,
) -> Phase:
    now = datetime.now(UTC)
    return Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=phase_no,
        code=f"phase-{phase_no}",
        name=f"Phase {phase_no}",
        status=status,
        enter_at=now if status != PhaseStatus.waiting else None,
        finish_at=now if status == PhaseStatus.completed else None,
        procurement_type=None,
        created_at=now,
        updated_at=now,
    )


def make_member(sub_project: SubProject, user: User) -> SubProjectMember:
    return SubProjectMember(
        id=uuid4(),
        sub_project_id=sub_project.id,
        user_id=user.id,
        role_in_project=SubProjectMemberRole.proj_member,
        joined_at=datetime.now(UTC),
    )


def make_document(sub_project: SubProject, phase: Phase, uploader: User) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        doc_no=str(uuid4()),
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        acceptance_step_id=None,
        doc_type="contract",
        file_name="contract.pdf",
        file_path=f"{sub_project.id}/{phase.id}/contract.pdf",
        file_size=256,
        version=1,
        is_latest=True,
        is_deleted=False,
        uploader_id=uploader.id,
        created_at=now,
        updated_at=now,
    )


def make_task(sub_project: SubProject, phase: Phase) -> Task:
    now = datetime.now(UTC)
    return Task(
        id=uuid4(),
        task_no="Z-2026-0001-ZX-001-T-001",
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        name="Keep completed task",
        plan_end_date=date(2026, 5, 20),
        status=TaskStatus.completed,
        created_at=now,
        updated_at=now,
    )


def make_request(
    *,
    phase: Phase,
    sub_project: SubProject,
    requester: User,
    status: RevokeRequestStatus = RevokeRequestStatus.pending,
) -> RevokeRequest:
    now = datetime.now(UTC)
    return RevokeRequest(
        id=uuid4(),
        phase_id=phase.id,
        sub_project_id=sub_project.id,
        requester_id=requester.id,
        reason="wrong document uploaded",
        status=status,
        reviewer_id=None,
        review_comment=None,
        reviewed_at=None,
        created_at=now,
        updated_at=now,
    )


def make_service() -> tuple[
    RevokeRequestService,
    InMemoryRevokeRequestRepository,
    InMemoryNotificationRepository,
    User,
    User,
    User,
    User,
    SubProject,
    Phase,
    Phase,
    Document,
    Task,
]:
    leader = make_user(UserRole.proj_leader, username="leader")
    uploader = make_user(UserRole.proj_member, username="uploader")
    other_member = make_user(UserRole.proj_member, username="member")
    admin = make_user(UserRole.admin, username="admin")
    sub_project = make_sub_project(leader)
    target_phase = make_phase(sub_project, phase_no=2, status=PhaseStatus.completed)
    next_phase = make_phase(sub_project, phase_no=3, status=PhaseStatus.in_progress)
    document = make_document(sub_project, target_phase, uploader)
    task = make_task(sub_project, target_phase)
    repository = InMemoryRevokeRequestRepository(
        documents=[document],
        members=[
            make_member(sub_project, leader),
            make_member(sub_project, uploader),
            make_member(sub_project, other_member),
        ],
        phases=[target_phase, next_phase],
        sub_projects=[sub_project],
        tasks=[task],
    )
    notification_repository = InMemoryNotificationRepository()
    service = RevokeRequestService(
        notification_service=NotificationService(repository=notification_repository),
        repository=repository,
    )
    return (
        service,
        repository,
        notification_repository,
        leader,
        uploader,
        other_member,
        admin,
        sub_project,
        target_phase,
        next_phase,
        document,
        task,
    )


def test_revoke_request_model_and_schema_match_requirements() -> None:
    assert [status.value for status in RevokeRequestStatus] == ["pending", "approved", "rejected"]
    assert [decision.value for decision in RevokeReviewDecision] == ["approve", "reject"]
    assert "revoke_requests" in Base.metadata.tables
    columns = set(RevokeRequest.__table__.c.keys())
    assert {
        "id",
        "phase_id",
        "sub_project_id",
        "requester_id",
        "reason",
        "status",
        "reviewer_id",
        "review_comment",
        "reviewed_at",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert isinstance(RevokeRequest.__table__, Table)

    manager = make_user(UserRole.proj_leader, username="manager")
    sub_project = make_sub_project(manager)
    phase = make_phase(
        sub_project,
        phase_no=2,
        status=PhaseStatus.completed,
    )
    request = make_request(
        phase=phase,
        requester=manager,
        sub_project=sub_project,
    )
    payload = RevokeRequestRead.model_validate(request).model_dump()
    assert payload["status"] == RevokeRequestStatus.pending


@pytest.mark.asyncio
async def test_submit_revoke_request_requires_completed_phase_and_project_leader() -> None:
    (
        service,
        repository,
        _notifications,
        leader,
        _uploader,
        _other,
        _admin,
        _sub,
        target,
        _next,
        _doc,
        _task,
    ) = make_service()

    request = await service.submit_request(
        actor=leader,
        payload=RevokeRequestCreate(phase_id=target.id, reason="wrong document uploaded"),
    )

    assert request.status == RevokeRequestStatus.pending
    assert request.sub_project_id == target.sub_project_id
    assert repository.revoke_requests == [request]

    target.status = PhaseStatus.in_progress
    with pytest.raises(BusinessException) as exc_info:
        await service.submit_request(
            actor=leader,
            payload=RevokeRequestCreate(phase_id=target.id, reason="not completed"),
        )
    assert exc_info.value.code == 3030

    outsider = make_user(UserRole.proj_leader, username="outsider")
    target.status = PhaseStatus.completed
    with pytest.raises(PermissionDeniedError):
        await service.submit_request(
            actor=outsider,
            payload=RevokeRequestCreate(phase_id=target.id, reason="not manager"),
        )


@pytest.mark.asyncio
async def test_submit_revoke_request_notifies_admin_and_same_dept_manager_only() -> None:
    (
        service,
        repository,
        notification_repository,
        leader,
        _uploader,
        other_member,
        admin,
        sub_project,
        target,
        _next,
        _doc,
        _task,
    ) = make_service()
    dept_manager = make_user(
        UserRole.dept_manager,
        dept_id=sub_project.dept_id,
        username="dept-manager",
    )
    other_dept_manager = make_user(
        UserRole.dept_manager,
        dept_id=uuid4(),
        username="other-dept-manager",
    )
    repository.users.extend([admin, dept_manager, other_dept_manager, other_member])

    request = await service.submit_request(
        actor=leader,
        payload=RevokeRequestCreate(phase_id=target.id, reason="wrong document uploaded"),
    )

    assert {item.scenario for item in notification_repository.notifications} == {
        "revoke_request_pending",
    }
    assert {item.receiver_id for item in notification_repository.notifications} == {
        admin.id,
        dept_manager.id,
    }
    assert all(item.source_id == str(request.id) for item in notification_repository.notifications)


@pytest.mark.asyncio
async def test_approve_revoke_request_restores_phase_soft_deletes_docs_and_limits_notifications(
) -> None:
    (
        service,
        repository,
        notification_repository,
        leader,
        uploader,
        other_member,
        admin,
        sub_project,
        target_phase,
        next_phase,
        document,
        task,
    ) = make_service()
    request = make_request(phase=target_phase, sub_project=sub_project, requester=leader)
    repository.revoke_requests.append(request)
    audit_writer = InMemoryAuditLogWriter()

    reviewed = await service.review_request(
        actor=admin,
        audit_context=AuditContext(actor_id=admin.id, request_id="req-1"),
        audit_writer=audit_writer,
        payload=RevokeRequestReview(
            decision=RevokeReviewDecision.approve,
            review_comment="approved",
        ),
        request_id=request.id,
    )

    assert reviewed.status == RevokeRequestStatus.approved
    assert reviewed.reviewer_id == admin.id
    assert target_phase.status == PhaseStatus.in_progress
    assert target_phase.finish_at is None
    assert next_phase.status == PhaseStatus.waiting
    assert next_phase.enter_at is None
    assert document.is_deleted is True
    assert task.status == TaskStatus.completed
    assert [history.to_status for history in repository.histories] == [
        PhaseStatus.in_progress,
        PhaseStatus.waiting,
    ]
    assert [history.note for history in repository.histories] == ["revoked", "revoke rollback"]

    receiver_ids = {
        notification.receiver_id for notification in notification_repository.notifications
    }
    assert receiver_ids == {leader.id, uploader.id}
    assert other_member.id not in receiver_ids
    assert {notification.scenario for notification in notification_repository.notifications} == {
        "revoke_result",
    }
    assert audit_writer.entries[0].action == "revoke_request.review"
    assert audit_writer.entries[0].extra["tasks_preserved"] is True


@pytest.mark.asyncio
async def test_reject_revoke_request_keeps_phase_and_documents_unchanged() -> None:
    (
        service,
        repository,
        _notifications,
        leader,
        _uploader,
        _other,
        admin,
        sub_project,
        target,
        next_phase,
        document,
        _task,
    ) = make_service()
    request = make_request(phase=target, sub_project=sub_project, requester=leader)
    repository.revoke_requests.append(request)

    reviewed = await service.review_request(
        actor=admin,
        payload=RevokeRequestReview(
            decision=RevokeReviewDecision.reject,
            review_comment="not enough reason",
        ),
        request_id=request.id,
    )

    assert reviewed.status == RevokeRequestStatus.rejected
    assert target.status == PhaseStatus.completed
    assert next_phase.status == PhaseStatus.in_progress
    assert document.is_deleted is False


def test_revoke_request_endpoints_submit_list_and_review() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    admin = make_user(UserRole.admin, username="admin")
    current_user = leader
    phase_id = uuid4()
    request = RevokeRequest(
        id=uuid4(),
        phase_id=phase_id,
        sub_project_id=uuid4(),
        requester_id=leader.id,
        reason="wrong file",
        status=RevokeRequestStatus.pending,
        reviewer_id=None,
        review_comment=None,
        reviewed_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeRevokeRequestService:
        async def list_requests(
            self,
            *,
            actor: User,
            status: RevokeRequestStatus | None = None,
        ) -> list[RevokeRequest]:
            assert actor.id == leader.id
            assert status is None
            return [request]

        async def submit_request(
            self,
            *,
            actor: User,
            payload: RevokeRequestCreate,
        ) -> RevokeRequest:
            assert actor.id == leader.id
            assert payload.phase_id == phase_id
            return request

        async def review_request(
            self,
            *,
            actor: User,
            request_id: UUID,
            payload: RevokeRequestReview,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> RevokeRequest:
                assert actor.id == admin.id
                assert request_id == request.id
                assert payload.decision == RevokeReviewDecision.approve
                assert audit_writer is not None
                assert audit_context is not None
                request.status = RevokeRequestStatus.approved
                return request

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return current_user

    async def fake_service() -> FakeRevokeRequestService:
        return FakeRevokeRequestService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_revoke_request_service] = fake_service
    client = TestClient(app)

    list_response = client.get("/api/v1/revoke-requests")
    create_response = client.post(
        "/api/v1/revoke-requests",
        json={"phase_id": str(phase_id), "reason": "wrong file"},
    )
    current_user = admin
    review_response = client.post(
        f"/api/v1/revoke-requests/{request.id}/review",
        json={"decision": "approve", "review_comment": "ok"},
    )

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == str(request.id)
    assert create_response.status_code == 200
    assert create_response.json()["data"]["phase_id"] == str(phase_id)
    assert review_response.status_code == 200
    assert review_response.json()["data"]["status"] == "approved"
