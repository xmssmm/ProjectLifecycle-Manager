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

from app.api.v1.main_projects import get_main_project_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.base import Base
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.schemas.main_projects import MainProjectCreate, MainProjectUpdate
from app.services.main_projects import InMemoryMainProjectRepository, MainProjectService


def make_user(role: UserRole, *, username: str = "user") -> User:
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


def make_payload(*, name: str = "主项目A") -> MainProjectCreate:
    return MainProjectCreate(
        name=name,
        dept_id=uuid4(),
        total_budget=Decimal("120000.00"),
        expected_finish_date=date(2026, 12, 31),
        remark="baseline",
    )


def make_service(
    *,
    projects: list[MainProject] | None = None,
    sub_projects: list[SubProject] | None = None,
    next_sequence: int = 1,
) -> tuple[MainProjectService, InMemoryMainProjectRepository]:
    repository = InMemoryMainProjectRepository(
        projects or [],
        sub_projects=sub_projects or [],
        next_sequence=next_sequence,
    )
    return (
        MainProjectService(
            repository=repository,
            today_provider=lambda: date(2026, 5, 10),
        ),
        repository,
    )


def test_main_project_model_matches_required_fields() -> None:
    assert "main_projects" in Base.metadata.tables
    assert [status.value for status in MainProjectStatus] == [
        "pending_review",
        "reviewing",
        "rejected",
        "not_started",
        "in_progress",
        "completed",
        "closed",
    ]

    table = MainProject.__table__
    assert isinstance(table, Table)
    assert {
        "project_no",
        "name",
        "dept_id",
        "status",
        "total_budget",
        "expected_finish_date",
        "spent_amount",
        "remark",
        "creator_id",
    }.issubset(set(table.c.keys()))
    assert isinstance(table.c.status.type, SqlEnum)
    assert table.c.status.type.enums == [status.value for status in MainProjectStatus]
    assert isinstance(table.c.total_budget.type, Numeric)
    assert table.c.total_budget.type.precision == 15
    assert table.c.total_budget.type.scale == 2


@pytest.mark.asyncio
async def test_create_main_project_generates_transaction_safe_project_no() -> None:
    actor = make_user(UserRole.dept_manager, username="dept")
    service, repository = make_service(next_sequence=42)

    project = await service.create_project(actor=actor, payload=make_payload())

    assert project in repository.projects
    assert project.project_no == "Z-2026-0042"
    assert project.status == MainProjectStatus.pending_review
    assert project.creator_id == actor.id
    assert project.spent_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_create_main_project_requires_dept_manager() -> None:
    actor = make_user(UserRole.admin, username="admin")
    service, _repository = make_service()

    with pytest.raises(PermissionDeniedError):
        await service.create_project(actor=actor, payload=make_payload())


@pytest.mark.asyncio
async def test_update_rejects_status_changes_and_pending_review_edits() -> None:
    actor = make_user(UserRole.dept_manager, username="dept")
    pending_project = await make_service()[0].create_project(actor=actor, payload=make_payload())
    service, _repository = make_service(projects=[pending_project])

    with pytest.raises(ValidationError):
        MainProjectUpdate.model_validate({"status": "closed"})

    with pytest.raises(BusinessException) as blocked:
        await service.update_project(
            actor=actor,
            project_id=pending_project.id,
            payload=MainProjectUpdate(name="不应修改"),
        )

    assert blocked.value.code == 3003
    assert pending_project.name == "主项目A"

    pending_project.status = MainProjectStatus.rejected
    updated = await service.update_project(
        actor=actor,
        project_id=pending_project.id,
        payload=MainProjectUpdate(name="退回后可修改", remark=None),
    )

    assert updated.name == "退回后可修改"
    assert updated.remark is None


@pytest.mark.asyncio
async def test_list_and_get_main_projects_require_view_all_role() -> None:
    dept_manager = make_user(UserRole.dept_manager, username="dept")
    member = make_user(UserRole.proj_member, username="member")
    service, _repository = make_service()
    project = await service.create_project(actor=dept_manager, payload=make_payload())

    items, total = await service.list_projects(actor=dept_manager, page=1, page_size=20)
    assert items == [project]
    assert total == 1
    assert await service.get_project(actor=dept_manager, project_id=project.id) == project

    with pytest.raises(PermissionDeniedError):
        await service.list_projects(actor=member, page=1, page_size=20)


def test_main_project_endpoints_return_standard_payloads() -> None:
    actor = make_user(UserRole.dept_manager, username="dept")
    project = MainProject(
        id=uuid4(),
        project_no="Z-2026-0001",
        name="主项目A",
        dept_id=uuid4(),
        status=MainProjectStatus.pending_review,
        total_budget=Decimal("120000.00"),
        expected_finish_date=date(2026, 12, 31),
        spent_amount=Decimal("0.00"),
        remark="baseline",
        creator_id=actor.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeMainProjectService:
        async def create_project(self, *, actor: User, payload: MainProjectCreate) -> MainProject:
            assert actor.id == actor.id
            assert payload.name == "主项目A"
            return project

        async def list_projects(
            self,
            *,
            actor: User,
            page: int,
            page_size: int,
        ) -> tuple[list[MainProject], int]:
            assert actor.role == UserRole.dept_manager
            assert page == 1
            assert page_size == 20
            return [project], 1

        async def get_project(self, *, actor: User, project_id: UUID) -> MainProject:
            assert actor.role == UserRole.dept_manager
            assert project_id == project.id
            return project

        async def update_project(
            self,
            *,
            actor: User,
            project_id: UUID,
            payload: MainProjectUpdate,
        ) -> MainProject:
            assert actor.role == UserRole.dept_manager
            assert project_id == project.id
            assert payload.name == "主项目B"
            project.name = "主项目B"
            return project

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return actor

    async def fake_main_project_service() -> FakeMainProjectService:
        return FakeMainProjectService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_main_project_service] = fake_main_project_service
    client = TestClient(app)

    create_response = client.post(
        "/api/v1/main-projects",
        json={
            "name": "主项目A",
            "dept_id": str(project.dept_id),
            "total_budget": "120000.00",
            "expected_finish_date": "2026-12-31",
            "remark": "baseline",
        },
    )
    list_response = client.get("/api/v1/main-projects")
    detail_response = client.get(f"/api/v1/main-projects/{project.id}")
    update_response = client.put(
        f"/api/v1/main-projects/{project.id}",
        json={"name": "主项目B"},
    )

    assert create_response.status_code == 200
    assert create_response.json()["data"]["project_no"] == "Z-2026-0001"
    assert list_response.json()["data"]["total"] == 1
    assert detail_response.json()["data"]["id"] == str(project.id)
    assert update_response.json()["data"]["name"] == "主项目B"


def make_sub_project(
    main_project: MainProject,
    *,
    status: SubProjectStatus,
) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no=f"{main_project.project_no}-ZX-001",
        name="子项目A",
        main_project_id=main_project.id,
        dept_id=main_project.dept_id,
        budget=Decimal("10000.00"),
        manager_id=uuid4(),
        creator_id=uuid4(),
        status=status,
        plan_end_date=None,
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_close_main_project_requires_all_sub_projects_closed_or_terminated() -> None:
    actor = make_user(UserRole.dept_manager, username="dept")
    project = await make_service()[0].create_project(actor=actor, payload=make_payload())
    project.status = MainProjectStatus.in_progress
    open_sub_project = make_sub_project(project, status=SubProjectStatus.in_progress)
    service, _repository = make_service(projects=[project], sub_projects=[open_sub_project])

    with pytest.raises(BusinessException) as blocked:
        await service.close_project(actor=actor, project_id=project.id)

    assert blocked.value.code == 3003
    assert blocked.value.data == {"open_sub_project_count": 1}
    assert project.status == MainProjectStatus.in_progress

    open_sub_project.status = SubProjectStatus.closed
    closed = await service.close_project(actor=actor, project_id=project.id)

    assert closed.status == MainProjectStatus.closed
    assert closed.closed_at is not None


@pytest.mark.asyncio
async def test_close_main_project_requires_dept_manager_role() -> None:
    actor = make_user(UserRole.dept_manager, username="dept")
    finance = make_user(UserRole.finance_manager, username="finance")
    project = await make_service()[0].create_project(actor=actor, payload=make_payload())
    project.status = MainProjectStatus.in_progress
    service, _repository = make_service(projects=[project])

    with pytest.raises(PermissionDeniedError):
        await service.close_project(actor=finance, project_id=project.id)
