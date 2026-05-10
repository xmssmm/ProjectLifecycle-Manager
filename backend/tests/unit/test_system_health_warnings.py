from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.system import get_system_health_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.core.security import hash_password
from app.main import create_app
from app.models.users import User, UserRole, UserStatus
from app.services.system_health import InMemoryRoleHealthReader, SystemHealthService


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
async def test_health_warnings_report_and_clear_dept_manager_shortage() -> None:
    shortage = SystemHealthService(role_reader=InMemoryRoleHealthReader(dept_manager_count=1))
    healthy = SystemHealthService(role_reader=InMemoryRoleHealthReader(dept_manager_count=2))

    shortage_warnings = await shortage.collect_warnings()
    healthy_warnings = await healthy.collect_warnings()

    assert shortage_warnings == [
        {
            "code": "dept_manager_minimum_not_met",
            "message": "生产环境至少需要 2 名综合部负责人",
            "data": {"current_count": 1, "required_count": 2},
        },
    ]
    assert healthy_warnings == []


def test_health_warnings_endpoint_is_admin_only() -> None:
    member = make_user(role=UserRole.proj_member)

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return member

    async def fake_system_health_service() -> SystemHealthService:
        return SystemHealthService(role_reader=InMemoryRoleHealthReader(dept_manager_count=0))

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_system_health_service] = fake_system_health_service
    client = TestClient(app)

    response = client.get("/api/v1/system/health-warnings")

    assert response.status_code == 403


def test_health_warnings_endpoint_returns_warning_payload_for_admin() -> None:
    admin = make_user()

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return admin

    async def fake_system_health_service() -> SystemHealthService:
        return SystemHealthService(role_reader=InMemoryRoleHealthReader(dept_manager_count=0))

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_system_health_service] = fake_system_health_service
    client = TestClient(app)

    response = client.get("/api/v1/system/health-warnings")

    assert response.status_code == 200
    assert response.json()["data"][0]["code"] == "dept_manager_minimum_not_met"
