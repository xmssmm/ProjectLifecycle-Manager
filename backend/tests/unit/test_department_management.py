from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.departments import get_department_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.core.security import hash_password
from app.main import create_app
from app.models.departments import Department
from app.models.users import User, UserRole, UserStatus
from app.schemas.departments import DepartmentCreate
from app.services.departments import DepartmentService, InMemoryDepartmentRepository


def make_department(*, code: str = "general", name: str = "综合部") -> Department:
    now = datetime.now(UTC)
    return Department(
        id=uuid4(),
        code=code,
        name=name,
        created_at=now,
        updated_at=now,
    )


def make_user(*, role: UserRole = UserRole.admin) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=f"{role.value}_{uuid4().hex[:6]}",
        email=None,
        password_hash=hash_password("StrongPass1!"),
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_admin_creates_department_and_duplicate_code_is_rejected() -> None:
    admin = make_user()
    existing = make_department(code="finance", name="财务部")
    repository = InMemoryDepartmentRepository([existing])
    service = DepartmentService(repository=repository)

    with pytest.raises(BusinessException) as duplicate:
        await service.create_department(
            actor=admin,
            payload=DepartmentCreate(code="finance", name="另一个财务部"),
        )
    assert duplicate.value.code == 4002

    created = await service.create_department(
        actor=admin,
        payload=DepartmentCreate(code="business", name="业务部"),
    )

    assert created in repository.departments
    assert created.code == "business"


@pytest.mark.asyncio
async def test_delete_department_with_active_users_is_rejected() -> None:
    admin = make_user()
    department = make_department()
    repository = InMemoryDepartmentRepository([department], active_user_counts={department.id: 1})
    service = DepartmentService(repository=repository)

    with pytest.raises(BusinessException) as blocked:
        await service.delete_department(actor=admin, department_id=department.id)

    assert blocked.value.code == 3003
    assert blocked.value.data == {"active_user_count": 1}
    assert department in repository.departments


def test_department_endpoints_allow_authenticated_list_and_reject_non_admin_create() -> None:
    member = make_user(role=UserRole.proj_member)
    department = make_department()

    class FakeDepartmentService:
        async def list_departments(self) -> list[Department]:
            return [department]

        async def create_department(
            self,
            *,
            actor: User,
            payload: DepartmentCreate,
        ) -> Department:
            _ = actor, payload
            return department

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return member

    async def fake_department_service() -> FakeDepartmentService:
        return FakeDepartmentService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_department_service] = fake_department_service
    client = TestClient(app)

    list_response = client.get("/api/v1/departments")
    create_response = client.post(
        "/api/v1/departments",
        json={"code": "business", "name": "业务部"},
    )

    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["code"] == department.code
    assert create_response.status_code == 403
    assert create_response.json()["code"] == PermissionDeniedError().code
