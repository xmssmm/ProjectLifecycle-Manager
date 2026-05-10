from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.dashboard import get_dashboard_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.users import User, UserRole, UserStatus


def make_user(role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username="leader",
        email="leader@example.local",
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def test_dashboard_endpoint_returns_role_scoped_payload() -> None:
    actor = make_user(UserRole.proj_leader)

    class FakeDashboardService:
        async def get_dashboard(self, *, actor: User, role_scope: UserRole) -> dict[str, object]:
            assert actor.role == UserRole.proj_leader
            assert role_scope == UserRole.proj_leader
            return {
                "role_scope": role_scope.value,
                "cache_ttl_seconds": 300,
                "metrics": {"managed_sub_projects": 2},
                "charts": {},
                "lists": {},
            }

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return actor

    async def fake_dashboard_service() -> FakeDashboardService:
        return FakeDashboardService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_dashboard_service] = fake_dashboard_service

    response = TestClient(app).get("/api/v1/dashboard/proj_leader")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "success",
        "data": {
            "role_scope": "proj_leader",
            "cache_ttl_seconds": 300,
            "metrics": {"managed_sub_projects": 2},
            "charts": {},
            "lists": {},
        },
    }
