from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base
from app.models.notifications import Notification
from app.services.notifications import InMemoryNotificationRepository, NotificationService


def fixed_business_date() -> date:
    return date(2026, 5, 10)


def make_service() -> tuple[NotificationService, InMemoryNotificationRepository]:
    repository = InMemoryNotificationRepository()
    service = NotificationService(
        repository=repository,
        business_date_provider=fixed_business_date,
    )
    return service, repository


def test_notification_table_has_required_columns_and_constraints() -> None:
    assert "notifications" in Base.metadata.tables

    table = Notification.__table__
    assert isinstance(table, Table)
    assert {
        "id",
        "receiver_id",
        "scenario",
        "source_id",
        "payload",
        "dedup_key",
        "read_at",
        "created_at",
        "updated_at",
    }.issubset(set(table.c.keys()))

    assert isinstance(table.c.payload.type, JSONB)
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("dedup_key",)
        for constraint in table.constraints
    )


@pytest.mark.asyncio
async def test_send_creates_notification_with_source_aware_dedup_key() -> None:
    service, repository = make_service()
    receiver_id = uuid4()
    source_id = uuid4()

    sent = await service.send(
        scenario="project_pending_review",
        receivers=[receiver_id],
        source_id=source_id,
        payload={"title": "待审核", "project_id": str(source_id)},
    )

    assert len(sent) == 1
    notification = sent[0]
    assert repository.notifications == [notification]
    assert notification.receiver_id == receiver_id
    assert notification.scenario == "project_pending_review"
    assert notification.source_id == str(source_id)
    assert notification.payload == {"title": "待审核", "project_id": str(source_id)}
    assert notification.dedup_key == (
        f"project_pending_review:{receiver_id}:{source_id}:20260510"
    )
    assert notification.read_at is None


@pytest.mark.asyncio
async def test_send_skips_existing_dedup_key_but_allows_different_source() -> None:
    service, repository = make_service()
    receiver_id = uuid4()
    source_id = uuid4()

    first = await service.send(
        scenario="task_due_today",
        receivers=[receiver_id],
        source_id=source_id,
        payload={"task": "A"},
    )
    duplicate = await service.send(
        scenario="task_due_today",
        receivers=[receiver_id],
        source_id=source_id,
        payload={"task": "A"},
    )
    other_source = await service.send(
        scenario="task_due_today",
        receivers=[receiver_id],
        source_id=uuid4(),
        payload={"task": "B"},
    )

    assert len(first) == 1
    assert duplicate == []
    assert len(other_source) == 1
    assert len(repository.notifications) == 2


@pytest.mark.asyncio
async def test_send_batches_receivers_and_removes_duplicate_receiver_ids() -> None:
    service, repository = make_service()
    receiver_a = uuid4()
    receiver_b = uuid4()
    source_id = UUID("00000000-0000-0000-0000-000000000123")

    sent = await service.send(
        scenario="phase_promoted",
        receivers=[receiver_a, receiver_b, receiver_a],
        source_id=source_id,
        payload={"phase_no": 2},
    )

    assert len(sent) == 2
    assert len(repository.notifications) == 2
    assert {notification.receiver_id for notification in sent} == {receiver_a, receiver_b}
    assert {
        notification.dedup_key for notification in sent
    } == {
        f"phase_promoted:{receiver_a}:{source_id}:20260510",
        f"phase_promoted:{receiver_b}:{source_id}:20260510",
    }
