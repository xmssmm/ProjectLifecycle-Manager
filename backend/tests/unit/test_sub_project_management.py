from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Numeric, Table

from app.api.v1.sub_projects import get_sub_project_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.base import Base
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.schemas.sub_projects import SubProjectCreate, SubProjectUpdate
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


def make_main_project(*, status: MainProjectStatus = MainProjectStatus.not_started) -> MainProject:
    now = datetime.now(UTC)
    return MainProject(
        id=uuid4(),
        project_no="Z-2026-0001",
        name="主项目A",
        dept_id=uuid4(),
        status=status,
        total_budget=Decimal("500000.00"),
        expected_finish_date=date(2026, 12, 31),
        spent_amount=Decimal("0.00"),
        remark=None,
        creator_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_payload(main_project: MainProject, *, name: str = "子项目A") -> SubProjectCreate:
    return SubProjectCreate(
        name=name,
        main_project_id=main_project.id,
        dept_id=uuid4(),
        budget=Decimal("100000.00"),
        plan_end_date=date(2026, 10, 31),
        remark="baseline",
    )


def make_service(
    *,
    main_projects: list[MainProject],
    sub_projects: list[SubProject] | None = None,
    next_sequence: int = 1,
) -> tuple[SubProjectService, InMemorySubProjectRepository]:
    repository = InMemorySubProjectRepository(
        main_projects=main_projects,
        sub_projects=sub_projects or [],
        next_sequences={main_projects[0].id: next_sequence} if main_projects else {},
    )
    return SubProjectService(repository=repository), repository


def test_sub_project_model_matches_required_fields() -> None:
    assert "sub_projects" in Base.metadata.tables
    assert [status.value for status in SubProjectStatus] == [
        "pending_review",
        "reviewing",
        "rejected",
        "not_started",
        "in_progress",
        "completed",
        "closed",
        "terminated",
    ]

    table = SubProject.__table__
    assert isinstance(table, Table)
    assert {
        "project_no",
        "name",
        "main_project_id",
        "dept_id",
        "budget",
        "manager_id",
        "creator_id",
        "status",
        "plan_end_date",
        "actual_end_date",
        "spent_amount",
    }.issubset(set(table.c.keys()))
    assert isinstance(table.c.status.type, SqlEnum)
    assert table.c.status.type.enums == [status.value for status in SubProjectStatus]
    assert isinstance(table.c.budget.type, Numeric)
    assert table.c.budget.type.precision == 15
    assert table.c.budget.type.scale == 2


@pytest.mark.asyncio
async def test_create_sub_project_generates_main_scoped_project_no() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    main_project = make_main_project()
    service, repository = make_service(main_projects=[main_project], next_sequence=7)

    sub_project = await service.create_sub_project(
        actor=leader,
        payload=make_payload(main_project),
    )

    assert sub_project in repository.sub_projects
    assert sub_project.project_no == "Z-2026-0001-ZX-007"
    assert sub_project.status == SubProjectStatus.pending_review
    assert sub_project.manager_id == leader.id
    assert sub_project.creator_id == leader.id
    assert sub_project.spent_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_create_sub_project_requires_proj_leader_and_open_main_project() -> None:
    member = make_user(UserRole.proj_member, username="member")
    leader = make_user(UserRole.proj_leader, username="leader")
    closed_main_project = make_main_project(status=MainProjectStatus.closed)
    service, _repository = make_service(main_projects=[closed_main_project])

    with pytest.raises(PermissionDeniedError):
        await service.create_sub_project(actor=member, payload=make_payload(closed_main_project))

    with pytest.raises(BusinessException) as invalid_main_status:
        await service.create_sub_project(actor=leader, payload=make_payload(closed_main_project))

    assert invalid_main_status.value.code == 3003


@pytest.mark.asyncio
async def test_update_sub_project_rejects_status_changes_and_pending_review_edits() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    main_project = make_main_project()
    service, _repository = make_service(main_projects=[main_project])
    sub_project = await service.create_sub_project(
        actor=leader,
        payload=make_payload(main_project),
    )

    with pytest.raises(ValidationError):
        SubProjectUpdate.model_validate({"status": "closed"})

    with pytest.raises(BusinessException) as blocked:
        await service.update_sub_project(
            actor=leader,
            sub_project_id=sub_project.id,
            payload=SubProjectUpdate(name="不应修改"),
        )
    assert blocked.value.code == 3003

    sub_project.status = SubProjectStatus.rejected
    updated = await service.update_sub_project(
        actor=leader,
        sub_project_id=sub_project.id,
        payload=SubProjectUpdate(name="退回后可修改", remark=None),
    )

    assert updated.name == "退回后可修改"
    assert updated.remark is None


@pytest.mark.asyncio
async def test_list_sub_projects_filters_by_role() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    other_leader = make_user(UserRole.proj_leader, username="other")
    finance = make_user(UserRole.finance_manager, username="finance")
    main_project = make_main_project()
    service, repository = make_service(main_projects=[main_project])
    mine = await service.create_sub_project(actor=leader, payload=make_payload(main_project))
    other = await service.create_sub_project(
        actor=other_leader,
        payload=make_payload(main_project, name="子项目B"),
    )
    other.status = SubProjectStatus.rejected
    repository.next_sequences[main_project.id] = 3

    mine_items, mine_total = await service.list_sub_projects(actor=leader, page=1, page_size=20)
    all_items, all_total = await service.list_sub_projects(actor=finance, page=1, page_size=20)

    assert mine_items == [mine]
    assert mine_total == 1
    assert set(all_items) == {mine, other}
    assert all_total == 2


def test_sub_project_endpoints_return_standard_payloads() -> None:
    leader = make_user(UserRole.proj_leader, username="leader")
    main_project = make_main_project()
    sub_project = SubProject(
        id=uuid4(),
        project_no="Z-2026-0001-ZX-001",
        name="子项目A",
        main_project_id=main_project.id,
        dept_id=uuid4(),
        budget=Decimal("100000.00"),
        manager_id=leader.id,
        creator_id=leader.id,
        status=SubProjectStatus.pending_review,
        plan_end_date=date(2026, 10, 31),
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark="baseline",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeSubProjectService:
        async def create_sub_project(self, *, actor: User, payload: SubProjectCreate) -> SubProject:
            assert actor.id == leader.id
            assert payload.name == "子项目A"
            return sub_project

        async def list_sub_projects(
            self,
            *,
            actor: User,
            page: int,
            page_size: int,
        ) -> tuple[list[SubProject], int]:
            assert actor.id == leader.id
            assert page == 1
            assert page_size == 20
            return [sub_project], 1

        async def get_sub_project(self, *, actor: User, sub_project_id: UUID) -> SubProject:
            assert actor.id == leader.id
            assert sub_project_id == sub_project.id
            return sub_project

        async def update_sub_project(
            self,
            *,
            actor: User,
            sub_project_id: UUID,
            payload: SubProjectUpdate,
        ) -> SubProject:
            assert actor.id == leader.id
            assert sub_project_id == sub_project.id
            assert payload.name == "子项目B"
            sub_project.name = "子项目B"
            return sub_project

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return leader

    async def fake_sub_project_service() -> FakeSubProjectService:
        return FakeSubProjectService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_sub_project_service] = fake_sub_project_service
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/sub-projects",
        json={
            "name": "子项目A",
            "main_project_id": str(main_project.id),
            "dept_id": str(sub_project.dept_id),
            "budget": "100000.00",
            "plan_end_date": "2026-10-31",
            "remark": "baseline",
        },
    )
    list_response = client.get("/api/v1/sub-projects")
    detail_response = client.get(f"/api/v1/sub-projects/{sub_project.id}")
    update_response = client.put(
        f"/api/v1/sub-projects/{sub_project.id}",
        json={"name": "子项目B"},
    )

    assert create_response.status_code == 200
    assert create_response.json()["data"]["project_no"] == "Z-2026-0001-ZX-001"
    assert list_response.json()["data"]["total"] == 1
    assert detail_response.json()["data"]["id"] == str(sub_project.id)
    assert update_response.json()["data"]["name"] == "子项目B"
