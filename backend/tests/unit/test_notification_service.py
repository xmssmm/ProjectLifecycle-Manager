from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.api.v1.notifications import get_notification_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.base import Base
from app.models.notifications import Notification, NotificationPreference
from app.models.users import User, UserRole, UserStatus
from app.services.notifications import (
    InMemoryNotificationRepository,
    NotificationPage,
    NotificationPreferenceState,
    NotificationService,
)


def fixed_business_date() -> date:
    return date(2026, 5, 10)


def make_service() -> tuple[NotificationService, InMemoryNotificationRepository]:
    repository = InMemoryNotificationRepository()
    service = NotificationService(
        repository=repository,
        business_date_provider=fixed_business_date,
    )
    return service, repository


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username="member",
        email="member@example.local",
        password_hash="hashed",
        role=UserRole.proj_member,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_notification(
    *,
    receiver_id: UUID,
    created_at: datetime,
    read_at: datetime | None = None,
) -> Notification:
    return Notification(
        id=uuid4(),
        receiver_id=receiver_id,
        scenario="task_assigned",
        source_id=str(uuid4()),
        payload={"title": "Task"},
        dedup_key=str(uuid4()),
        read_at=read_at,
        created_at=created_at,
        updated_at=created_at,
    )


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


def test_notification_preference_table_has_required_columns_and_constraints() -> None:
    assert "user_notification_preferences" in Base.metadata.tables

    table = NotificationPreference.__table__
    assert isinstance(table, Table)
    assert {
        "id",
        "user_id",
        "scenario",
        "enabled",
        "created_at",
        "updated_at",
    }.issubset(set(table.c.keys()))

    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("user_id", "scenario")
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
async def test_send_respects_notification_preferences_per_receiver() -> None:
    service, repository = make_service()
    enabled_receiver = uuid4()
    disabled_receiver = uuid4()
    source_id = uuid4()
    repository.preferences[(disabled_receiver, "task_assigned")] = False

    sent = await service.send(
        scenario="task_assigned",
        receivers=[enabled_receiver, disabled_receiver],
        source_id=source_id,
        payload={"task": "A"},
    )

    assert [notification.receiver_id for notification in sent] == [enabled_receiver]
    assert [notification.receiver_id for notification in repository.notifications] == [
        enabled_receiver,
    ]

    repository.preferences[(disabled_receiver, "task_assigned")] = True
    reenabled = await service.send(
        scenario="task_assigned",
        receivers=[enabled_receiver, disabled_receiver],
        source_id=source_id,
        payload={"task": "A"},
    )

    assert [notification.receiver_id for notification in reenabled] == [disabled_receiver]


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


@pytest.mark.asyncio
async def test_query_notifications_filters_unread_and_marks_read() -> None:
    user = make_user()
    now = datetime.now(UTC)
    unread = make_notification(receiver_id=user.id, created_at=now)
    read = make_notification(
        receiver_id=user.id,
        created_at=now - timedelta(days=1),
        read_at=now,
    )
    other_user = make_notification(receiver_id=uuid4(), created_at=now)
    repository = InMemoryNotificationRepository([unread, read, other_user])
    service = NotificationService(repository=repository)

    page = await service.list_notifications(actor=user, unread=True, page=1, page_size=20)
    count = await service.unread_count(actor=user)
    marked = await service.mark_read(actor=user, notification_id=unread.id)

    assert page.items == [unread]
    assert page.total == 1
    assert count == 1
    assert marked.read_at is not None
    assert await service.unread_count(actor=user) == 0


@pytest.mark.asyncio
async def test_mark_all_read_only_updates_current_user_unread_notifications() -> None:
    user = make_user()
    now = datetime.now(UTC)
    first = make_notification(receiver_id=user.id, created_at=now)
    second = make_notification(receiver_id=user.id, created_at=now - timedelta(minutes=1))
    other_user = make_notification(receiver_id=uuid4(), created_at=now)
    repository = InMemoryNotificationRepository([first, second, other_user])
    service = NotificationService(repository=repository)

    read_count = await service.mark_all_read(actor=user)

    assert read_count == 2
    assert first.read_at is not None
    assert second.read_at is not None
    assert other_user.read_at is None


@pytest.mark.asyncio
async def test_lists_and_updates_notification_preferences() -> None:
    user = make_user()
    service, repository = make_service()

    defaults = await service.list_preferences(actor=user)

    assert all(item.enabled for item in defaults)
    assert {item.scenario for item in defaults}.issuperset(
        {
            "project_pending_review",
            "task_assigned",
            "task_overdue_escalation",
            "handover_completed",
        },
    )

    updated = await service.update_preferences(
        actor=user,
        preferences={"task_assigned": False, "project_pending_review": True},
    )

    assert repository.preferences[(user.id, "task_assigned")] is False
    assert repository.preferences[(user.id, "project_pending_review")] is True
    assert next(item for item in updated if item.scenario == "task_assigned").enabled is False


def test_notification_endpoints_list_count_and_mark_read() -> None:
    user = make_user()
    notification = make_notification(receiver_id=user.id, created_at=datetime.now(UTC))

    class FakeNotificationService:
        async def list_notifications(
            self,
            *,
            actor: User,
            unread: bool | None,
            page: int,
            page_size: int,
        ) -> NotificationPage:
            assert actor.id == user.id
            assert unread is True
            assert page == 1
            assert page_size == 10
            return NotificationPage(items=[notification], page=page, page_size=page_size, total=1)

        async def unread_count(self, *, actor: User) -> int:
            assert actor.id == user.id
            return 1

        async def mark_read(self, *, actor: User, notification_id: UUID) -> Notification:
            assert actor.id == user.id
            assert notification_id == notification.id
            notification.read_at = datetime.now(UTC)
            return notification

        async def mark_all_read(self, *, actor: User) -> int:
            assert actor.id == user.id
            return 3

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> FakeNotificationService:
        return FakeNotificationService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_notification_service] = fake_service
    client = TestClient(app)

    list_response = client.get("/api/v1/notifications?unread=true&page=1&page_size=10")
    count_response = client.get("/api/v1/notifications/unread-count")
    read_response = client.post(f"/api/v1/notifications/{notification.id}/read")
    read_all_response = client.post("/api/v1/notifications/read-all")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == str(notification.id)
    assert list_response.json()["data"]["total"] == 1
    assert count_response.status_code == 200
    assert count_response.json()["data"]["count"] == 1
    assert read_response.status_code == 200
    assert read_response.json()["data"]["read_at"] is not None
    assert read_all_response.status_code == 200
    assert read_all_response.json()["data"]["read_count"] == 3


def test_notification_preference_endpoints_list_and_update() -> None:
    user = make_user()

    class FakeNotificationService:
        async def list_preferences(self, *, actor: User) -> list[NotificationPreferenceState]:
            assert actor.id == user.id
            return [
                NotificationPreferenceState(
                    scenario="task_assigned",
                    label="任务分配",
                    description="任务执行人收到任务分配提醒",
                    direct_related=True,
                    enabled=False,
                ),
            ]

        async def update_preferences(
            self,
            *,
            actor: User,
            preferences: dict[str, bool],
        ) -> list[NotificationPreferenceState]:
            assert actor.id == user.id
            assert preferences == {"task_assigned": True}
            return [
                NotificationPreferenceState(
                    scenario="task_assigned",
                    label="任务分配",
                    description="任务执行人收到任务分配提醒",
                    direct_related=True,
                    enabled=True,
                ),
            ]

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> FakeNotificationService:
        return FakeNotificationService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_notification_service] = fake_service
    client = TestClient(app)

    list_response = client.get("/api/v1/notifications/preferences")
    update_response = client.put(
        "/api/v1/notifications/preferences",
        json={"preferences": [{"scenario": "task_assigned", "enabled": True}]},
    )

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0] == {
        "scenario": "task_assigned",
        "label": "任务分配",
        "description": "任务执行人收到任务分配提醒",
        "direct_related": True,
        "enabled": False,
    }
    assert update_response.status_code == 200
    assert update_response.json()["data"]["items"][0]["enabled"] is True
