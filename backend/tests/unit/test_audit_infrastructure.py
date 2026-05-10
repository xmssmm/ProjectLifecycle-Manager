from __future__ import annotations

from datetime import date
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import JSONB

from app.core.middleware import RequestIdMiddleware
from app.models.audit_logs import AuditLog
from app.models.base import Base
from app.services.audit import (
    AuditContext,
    InMemoryAuditLogWriter,
    audited,
    build_monthly_partition_specs,
    get_audit_context,
)


def test_audit_log_table_is_partitioned_append_only_shape() -> None:
    assert "audit_logs" in Base.metadata.tables

    table = AuditLog.__table__
    assert isinstance(table, Table)
    assert table.dialect_options["postgresql"]["partition_by"] == "RANGE (created_at)"
    assert [column.name for column in table.primary_key.columns] == ["id", "created_at"]
    assert {
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "before_state",
        "after_state",
        "ip_address",
        "user_agent",
        "extra",
        "request_id",
        "created_at",
        "updated_at",
    }.issubset(set(table.c.keys()))
    assert isinstance(table.c.before_state.type, JSONB)
    assert isinstance(table.c.after_state.type, JSONB)
    assert isinstance(table.c.extra.type, JSONB)


def test_monthly_partition_specs_cover_current_and_future_12_months() -> None:
    specs = build_monthly_partition_specs(date(2026, 5, 10), months_ahead=12)

    assert len(specs) == 13
    assert specs[0].name == "audit_logs_202605"
    assert specs[0].start == date(2026, 5, 1)
    assert specs[0].end == date(2026, 6, 1)
    assert specs[-1].name == "audit_logs_202705"


def test_request_middleware_injects_audit_context() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/context")
    async def context() -> dict[str, object | None]:
        audit_context = get_audit_context()
        assert audit_context is not None
        return {
            "actor_id": str(audit_context.actor_id) if audit_context.actor_id else None,
            "ip_address": audit_context.ip_address,
            "user_agent": audit_context.user_agent,
            "request_id": audit_context.request_id,
        }

    response = TestClient(app).get(
        "/context",
        headers={"X-Request-ID": "req-123", "User-Agent": "pytest-agent"},
    )

    assert response.status_code == 200
    assert response.json()["actor_id"] is None
    assert response.json()["user_agent"] == "pytest-agent"
    assert response.json()["request_id"] == "req-123"


@pytest.mark.asyncio
async def test_audited_decorator_records_before_after_diff_and_context() -> None:
    writer = InMemoryAuditLogWriter()
    actor_id = uuid4()
    target_id = uuid4()
    context = AuditContext(
        actor_id=actor_id,
        ip_address="127.0.0.1",
        user_agent="pytest-agent",
        request_id="req-456",
    )

    @audited("user.update", target_type="user")
    async def update_email(
        user_id: str,
        *,
        audit_writer: InMemoryAuditLogWriter,
        audit_context: AuditContext,
        audit_before_state: dict[str, object],
    ) -> dict[str, object]:
        _ = audit_writer, audit_context, audit_before_state
        return {"id": user_id, "email": "new@example.local", "role": "admin"}

    started_at = perf_counter()
    result = await update_email(
        str(target_id),
        audit_writer=writer,
        audit_context=context,
        audit_before_state={
            "id": str(target_id),
            "email": "old@example.local",
            "role": "admin",
        },
    )
    elapsed_ms = (perf_counter() - started_at) * 1000

    assert result["email"] == "new@example.local"
    assert elapsed_ms <= 50
    assert len(writer.entries) == 1
    entry = writer.entries[0]
    assert entry.actor_id == actor_id
    assert entry.action == "user.update"
    assert entry.target_type == "user"
    assert entry.target_id == str(target_id)
    assert entry.before_state["email"] == "old@example.local"
    assert entry.after_state["email"] == "new@example.local"
    assert entry.ip_address == "127.0.0.1"
    assert entry.user_agent == "pytest-agent"
    assert entry.request_id == "req-456"
    assert entry.extra["modified_fields"] == {
        "email": {"before": "old@example.local", "after": "new@example.local"},
    }
