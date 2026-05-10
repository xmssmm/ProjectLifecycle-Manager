from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table

from app.api.v1.sub_projects import get_sub_project_service
from app.api.v1.users import get_project_handover_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.base import Base
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectHandover,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.users import User, UserRole, UserStatus
from app.schemas.sub_projects import (
    SubProjectBatchHandoverItem,
    SubProjectHandoverRequest,
)
from app.services.audit import InMemoryAuditLogWriter
from app.services.notifications import InMemoryNotificationRepository, NotificationService
from app.services.sub_projects import InMemorySubProjectRepository, SubProjectService


def make_user(role: UserRole, *, username: str, status: UserStatus = UserStatus.active) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=status,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_main_project() -> MainProject:
    now = datetime.now(UTC)
    return MainProject(
        id=uuid4(),
        project_no="Z-2026-0001",
        name="主项目A",
        dept_id=uuid4(),
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
    status: SubProjectStatus = SubProjectStatus.in_progress,
    name: str = "子项目A",
) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no=f"{main_project.project_no}-ZX-{uuid4().hex[:3]}",
        name=name,
        main_project_id=main_project.id,
        dept_id=uuid4(),
        budget=Decimal("100000.00"),
        manager_id=manager.id,
        creator_id=manager.id,
        status=status,
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
) -> tuple[SubProjectService, InMemorySubProjectRepository, InMemoryNotificationRepository]:
    repository = InMemorySubProjectRepository(
        main_projects=main_projects,
        sub_projects=sub_projects,
        members=members,
        users=users,
    )
    notification_repository = InMemoryNotificationRepository()
    service = SubProjectService(
        repository=repository,
        notification_service=NotificationService(
            repository=notification_repository,
            business_date_provider=lambda: date(2026, 5, 10),
        ),
    )
    return service, repository, notification_repository


def test_sub_project_handover_model_matches_required_fields() -> None:
    assert "sub_project_handovers" in Base.metadata.tables
    table = SubProjectHandover.__table__
    assert isinstance(table, Table)
    assert {
        "id",
        "sub_project_id",
        "from_user_id",
        "to_user_id",
        "reason",
        "operator_id",
        "operated_at",
        "created_at",
        "updated_at",
    }.issubset(set(table.c.keys()))


@pytest.mark.asyncio
async def test_handover_transfers_manager_records_history_members_notifications_and_audit() -> None:
    admin = make_user(UserRole.admin, username="admin")
    old_leader = make_user(UserRole.proj_leader, username="old")
    new_leader = make_user(UserRole.proj_leader, username="new")
    member = make_user(UserRole.proj_member, username="member")
    main_project = make_main_project()
    sub_project = make_sub_project(main_project, old_leader)
    service, repository, notification_repository = make_service(
        users=[admin, old_leader, new_leader, member],
        main_projects=[main_project],
        sub_projects=[sub_project],
        members=[
            make_member(sub_project, old_leader, SubProjectMemberRole.proj_leader),
            make_member(sub_project, member, SubProjectMemberRole.proj_member),
        ],
    )
    audit_writer = InMemoryAuditLogWriter()

    handed_over = await service.handover_sub_project(
        actor=admin,
        sub_project_id=sub_project.id,
        payload=SubProjectHandoverRequest(to_user_id=new_leader.id, reason="负责人离职"),
        audit_writer=audit_writer,
    )

    assert handed_over.manager_id == new_leader.id
    assert repository.handovers[0].from_user_id == old_leader.id
    assert repository.handovers[0].to_user_id == new_leader.id
    assert repository.handovers[0].reason == "负责人离职"
    member_roles = {item.user_id: item.role_in_project for item in repository.members}
    assert member_roles[old_leader.id] == SubProjectMemberRole.proj_member
    assert member_roles[new_leader.id] == SubProjectMemberRole.proj_leader
    assert {item.receiver_id for item in notification_repository.notifications} == {
        old_leader.id,
        new_leader.id,
        member.id,
    }
    assert audit_writer.entries[0].action == "sub_project.handover"
    assert audit_writer.entries[0].extra["from_user_id"] == str(old_leader.id)
    assert audit_writer.entries[0].extra["to_user_id"] == str(new_leader.id)
    assert audit_writer.entries[0].extra["reason"] == "负责人离职"


@pytest.mark.asyncio
async def test_handover_rejects_non_admin_closed_project_and_invalid_new_leader() -> None:
    admin = make_user(UserRole.admin, username="admin")
    old_leader = make_user(UserRole.proj_leader, username="old")
    new_member = make_user(UserRole.proj_member, username="new-member")
    main_project = make_main_project()
    closed_project = make_sub_project(main_project, old_leader, status=SubProjectStatus.closed)
    active_project = make_sub_project(main_project, old_leader, status=SubProjectStatus.in_progress)
    service, _repository, _notification_repository = make_service(
        users=[admin, old_leader, new_member],
        main_projects=[main_project],
        sub_projects=[closed_project, active_project],
        members=[
            make_member(closed_project, old_leader, SubProjectMemberRole.proj_leader),
            make_member(active_project, old_leader, SubProjectMemberRole.proj_leader),
        ],
    )

    with pytest.raises(PermissionDeniedError):
        await service.handover_sub_project(
            actor=old_leader,
            sub_project_id=closed_project.id,
            payload=SubProjectHandoverRequest(to_user_id=new_member.id, reason="无权限"),
        )

    with pytest.raises(BusinessException) as closed_blocked:
        await service.handover_sub_project(
            actor=admin,
            sub_project_id=closed_project.id,
            payload=SubProjectHandoverRequest(to_user_id=new_member.id, reason="已结项"),
    )
    assert closed_blocked.value.code == 3003

    with pytest.raises(BusinessException) as invalid_new_leader:
        await service.handover_sub_project(
            actor=admin,
            sub_project_id=active_project.id,
            payload=SubProjectHandoverRequest(to_user_id=new_member.id, reason="角色不符"),
        )
    assert invalid_new_leader.value.code == 3003


@pytest.mark.asyncio
async def test_handover_does_not_notify_disabled_old_leader() -> None:
    admin = make_user(UserRole.admin, username="admin")
    old_leader = make_user(UserRole.proj_leader, username="old", status=UserStatus.disabled)
    new_leader = make_user(UserRole.proj_leader, username="new")
    member = make_user(UserRole.proj_member, username="member")
    main_project = make_main_project()
    sub_project = make_sub_project(main_project, old_leader)
    service, _repository, notification_repository = make_service(
        users=[admin, old_leader, new_leader, member],
        main_projects=[main_project],
        sub_projects=[sub_project],
        members=[
            make_member(sub_project, old_leader, SubProjectMemberRole.proj_leader),
            make_member(sub_project, member, SubProjectMemberRole.proj_member),
        ],
    )

    await service.handover_sub_project(
        actor=admin,
        sub_project_id=sub_project.id,
        payload=SubProjectHandoverRequest(to_user_id=new_leader.id, reason="历史遗留转交"),
    )

    assert {item.receiver_id for item in notification_repository.notifications} == {
        new_leader.id,
        member.id,
    }


@pytest.mark.asyncio
async def test_list_active_projects_and_batch_handover_skip_closed_projects() -> None:
    admin = make_user(UserRole.admin, username="admin")
    old_leader = make_user(UserRole.proj_leader, username="old")
    new_leader = make_user(UserRole.proj_leader, username="new")
    main_project = make_main_project()
    active_a = make_sub_project(main_project, old_leader, status=SubProjectStatus.not_started)
    active_b = make_sub_project(main_project, old_leader, status=SubProjectStatus.completed)
    closed = make_sub_project(main_project, old_leader, status=SubProjectStatus.closed)
    service, _repository, _notification_repository = make_service(
        users=[admin, old_leader, new_leader],
        main_projects=[main_project],
        sub_projects=[active_a, active_b, closed],
        members=[
            make_member(active_a, old_leader, SubProjectMemberRole.proj_leader),
            make_member(active_b, old_leader, SubProjectMemberRole.proj_leader),
            make_member(closed, old_leader, SubProjectMemberRole.proj_leader),
        ],
    )

    active_projects = await service.list_active_sub_projects_for_leader(
        actor=admin,
        user_id=old_leader.id,
    )
    handed_over = await service.batch_handover_sub_projects(
        actor=admin,
        from_user_id=old_leader.id,
        payload=[
            SubProjectBatchHandoverItem(
                sub_project_id=active_a.id,
                to_user_id=new_leader.id,
                reason="批量转交 A",
            ),
            SubProjectBatchHandoverItem(
                sub_project_id=active_b.id,
                to_user_id=new_leader.id,
                reason="批量转交 B",
            ),
        ],
    )

    assert {project.id for project in active_projects} == {active_a.id, active_b.id}
    assert [project.manager_id for project in handed_over] == [new_leader.id, new_leader.id]
    assert closed.manager_id == old_leader.id


def test_handover_endpoints_return_standard_payloads() -> None:
    admin = make_user(UserRole.admin, username="admin")
    old_leader = make_user(UserRole.proj_leader, username="old")
    new_leader = make_user(UserRole.proj_leader, username="new")
    main_project = make_main_project()
    sub_project = make_sub_project(main_project, old_leader)

    class FakeProjectHandoverService:
        async def list_active_sub_projects_for_leader(
            self,
            *,
            actor: User,
            user_id: UUID,
        ) -> list[SubProject]:
            assert actor.id == admin.id
            assert user_id == old_leader.id
            return [sub_project]

        async def batch_handover_sub_projects(
            self,
            *,
            actor: User,
            from_user_id: UUID,
            payload: list[SubProjectBatchHandoverItem],
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> list[SubProject]:
            _ = audit_writer, audit_context
            assert actor.id == admin.id
            assert from_user_id == old_leader.id
            assert payload[0].to_user_id == new_leader.id
            sub_project.manager_id = new_leader.id
            return [sub_project]

    class FakeSubProjectService(FakeProjectHandoverService):
        async def handover_sub_project(
            self,
            *,
            actor: User,
            sub_project_id: UUID,
            payload: SubProjectHandoverRequest,
            audit_writer: object | None = None,
            audit_context: object | None = None,
        ) -> SubProject:
            _ = audit_writer, audit_context
            assert actor.id == admin.id
            assert sub_project_id == sub_project.id
            assert payload.to_user_id == new_leader.id
            sub_project.manager_id = new_leader.id
            return sub_project

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return admin

    async def fake_user_handover_service() -> FakeProjectHandoverService:
        return FakeProjectHandoverService()

    async def fake_sub_project_service() -> FakeSubProjectService:
        return FakeSubProjectService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_project_handover_service] = fake_user_handover_service
    app.dependency_overrides[get_sub_project_service] = fake_sub_project_service
    client = TestClient(app)

    active_response = client.get(f"/api/v1/users/{old_leader.id}/active-sub-projects")
    handover_response = client.post(
        f"/api/v1/sub-projects/{sub_project.id}/handover",
        json={"to_user_id": str(new_leader.id), "reason": "接口转交"},
    )
    batch_response = client.post(
        f"/api/v1/users/{old_leader.id}/batch-handover",
        json=[
            {
                "sub_project_id": str(sub_project.id),
                "to_user_id": str(new_leader.id),
                "reason": "批量转交",
            },
        ],
    )

    assert active_response.status_code == 200
    assert active_response.json()["data"]["total"] == 1
    assert handover_response.json()["data"]["manager_id"] == str(new_leader.id)
    assert batch_response.json()["data"]["items"][0]["manager_id"] == str(new_leader.id)
