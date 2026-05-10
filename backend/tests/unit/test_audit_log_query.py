from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.audit_logs import get_audit_log_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import PermissionDeniedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.audit_logs import AuditLog
from app.models.users import User, UserRole, UserStatus
from app.services.audit_logs import (
    AuditLogPage,
    AuditLogQuery,
    AuditLogService,
    InMemoryAuditLogRepository,
)


def make_user(role: UserRole = UserRole.admin) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=f"{role.value}-user",
        email=None,
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_log(
    *,
    actor_id: UUID | None,
    action: str,
    created_at: datetime,
    target_id: str = "target-1",
    target_type: str = "user",
) -> AuditLog:
    return AuditLog(
        id=uuid4(),
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_state={"before": True},
        after_state={"after": True},
        ip_address="127.0.0.1",
        user_agent="pytest",
        extra={"reason": "unit"},
        request_id="req-1",
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.mark.asyncio
async def test_audit_log_query_filters_cross_month_logs_and_sorts_desc() -> None:
    admin = make_user()
    actor_id = uuid4()
    may_log = make_log(
        actor_id=actor_id,
        action="user.update",
        created_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
    )
    april_log = make_log(
        actor_id=actor_id,
        action="user.update",
        created_at=datetime(2026, 4, 30, 23, 30, tzinfo=UTC),
    )
    ignored_action = make_log(
        actor_id=actor_id,
        action="user.delete",
        created_at=datetime(2026, 5, 9, 9, 0, tzinfo=UTC),
    )
    ignored_actor = make_log(
        actor_id=uuid4(),
        action="user.update",
        created_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )
    service = AuditLogService(
        repository=InMemoryAuditLogRepository(
            [april_log, ignored_action, may_log, ignored_actor],
        ),
    )

    page = await service.list_logs(
        actor=admin,
        query=AuditLogQuery(
            actor_id=actor_id,
            action="user.update",
            created_from=datetime(2026, 4, 1, tzinfo=UTC),
            created_to=datetime(2026, 6, 1, tzinfo=UTC),
            page=1,
            page_size=20,
            target_id="target-1",
            target_type="user",
        ),
    )

    assert page.items == [may_log, april_log]
    assert page.total == 2


@pytest.mark.asyncio
async def test_audit_log_query_is_admin_only_and_paginates_large_data_under_one_second() -> None:
    admin = make_user()
    member = make_user(UserRole.proj_member)
    now = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)
    logs = [
        make_log(
            actor_id=admin.id,
            action="bulk.update",
            created_at=now - timedelta(seconds=index),
            target_id=f"target-{index}",
        )
        for index in range(2500)
    ]
    service = AuditLogService(repository=InMemoryAuditLogRepository(logs))

    with pytest.raises(PermissionDeniedError):
        await service.list_logs(actor=member, query=AuditLogQuery())

    started_at = perf_counter()
    page = await service.list_logs(actor=admin, query=AuditLogQuery(page=2, page_size=50))
    elapsed = perf_counter() - started_at

    assert elapsed <= 1
    assert len(page.items) == 50
    assert page.total == 2500
    assert page.items[0].target_id == "target-50"


def test_audit_log_endpoint_maps_filters_and_serializes_page() -> None:
    admin = make_user()
    audit_log = make_log(
        actor_id=admin.id,
        action="user.update",
        created_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
    )

    class FakeAuditLogService:
        async def list_logs(self, *, actor: User, query: AuditLogQuery) -> AuditLogPage:
            assert actor.id == admin.id
            assert query.actor_id == admin.id
            assert query.action == "user.update"
            assert query.target_type == "user"
            assert query.target_id == "target-1"
            assert query.created_from == datetime(2026, 5, 1, tzinfo=UTC)
            assert query.created_to == datetime(2026, 6, 1, tzinfo=UTC)
            assert query.page == 1
            assert query.page_size == 10
            return AuditLogPage(items=[audit_log], page=1, page_size=10, total=1)

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return admin

    async def fake_service() -> FakeAuditLogService:
        return FakeAuditLogService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_audit_log_service] = fake_service
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit-logs",
        params={
            "actor_id": str(admin.id),
            "action": "user.update",
            "target_type": "user",
            "target_id": "target-1",
            "created_from": "2026-05-01T00:00:00Z",
            "created_to": "2026-06-01T00:00:00Z",
            "page": 1,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == str(audit_log.id)
    assert payload["items"][0]["action"] == "user.update"
