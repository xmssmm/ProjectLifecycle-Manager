from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Notification

BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


def current_business_date() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()


class NotificationRepository(Protocol):
    async def existing_dedup_keys(self, dedup_keys: Sequence[str]) -> set[str]:
        ...

    def add_many(self, notifications: Sequence[Notification]) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        ...


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def existing_dedup_keys(self, dedup_keys: Sequence[str]) -> set[str]:
        if not dedup_keys:
            return set()

        result = await self._session.scalars(
            select(Notification.dedup_key).where(Notification.dedup_key.in_(dedup_keys)),
        )
        return set(result.all())

    def add_many(self, notifications: Sequence[Notification]) -> None:
        self._session.add_all(list(notifications))

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        for notification in notifications:
            await self._session.refresh(notification)


class InMemoryNotificationRepository:
    def __init__(self, notifications: Sequence[Notification] | None = None) -> None:
        self.notifications = list(notifications or [])

    async def existing_dedup_keys(self, dedup_keys: Sequence[str]) -> set[str]:
        requested = set(dedup_keys)
        return {
            notification.dedup_key
            for notification in self.notifications
            if notification.dedup_key in requested
        }

    def add_many(self, notifications: Sequence[Notification]) -> None:
        self.notifications.extend(notifications)

    async def commit(self) -> None:
        return None

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        _ = notifications
        return None


class NotificationService:
    def __init__(
        self,
        *,
        repository: NotificationRepository,
        business_date_provider: Callable[[], date] = current_business_date,
    ) -> None:
        self._repository = repository
        self._business_date_provider = business_date_provider

    async def send(
        self,
        *,
        scenario: str,
        receivers: Sequence[UUID],
        source_id: UUID | str,
        payload: Mapping[str, object] | None = None,
    ) -> list[Notification]:
        """Create unread in-app notifications, skipping same-day duplicates."""
        receiver_ids = self._unique_receivers(receivers)
        if not receiver_ids:
            return []

        source_key = str(source_id)
        business_date = self._business_date_provider()
        dedup_by_receiver = {
            receiver_id: self.build_dedup_key(
                scenario=scenario,
                receiver_id=receiver_id,
                source_id=source_key,
                business_date=business_date,
            )
            for receiver_id in receiver_ids
        }
        existing = await self._repository.existing_dedup_keys(list(dedup_by_receiver.values()))
        now = datetime.now(UTC)
        notification_payload = dict(payload or {})

        notifications = [
            Notification(
                receiver_id=receiver_id,
                scenario=scenario,
                source_id=source_key,
                payload=notification_payload,
                dedup_key=dedup_key,
                read_at=None,
                created_at=now,
                updated_at=now,
            )
            for receiver_id, dedup_key in dedup_by_receiver.items()
            if dedup_key not in existing
        ]

        if not notifications:
            return []

        self._repository.add_many(notifications)
        await self._repository.commit()
        await self._repository.refresh_many(notifications)
        return notifications

    @staticmethod
    def build_dedup_key(
        *,
        scenario: str,
        receiver_id: UUID,
        source_id: str,
        business_date: date,
    ) -> str:
        return f"{scenario}:{receiver_id}:{source_id}:{business_date:%Y%m%d}"

    @staticmethod
    def _unique_receivers(receivers: Sequence[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        unique_receivers: list[UUID] = []
        for receiver_id in receivers:
            if receiver_id in seen:
                continue
            seen.add(receiver_id)
            unique_receivers.append(receiver_id)
        return unique_receivers
