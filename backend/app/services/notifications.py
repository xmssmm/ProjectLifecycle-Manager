from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError, ValidationFailedError
from app.models.notifications import Notification
from app.models.users import User

BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


def current_business_date() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()


@dataclass(frozen=True)
class NotificationPage:
    items: list[Notification]
    page: int
    page_size: int
    total: int


class NotificationRepository(Protocol):
    async def existing_dedup_keys(self, dedup_keys: Sequence[str]) -> set[str]:
        ...

    async def list_notifications(
        self,
        *,
        receiver_id: UUID,
        unread: bool | None,
        page: int,
        page_size: int,
    ) -> NotificationPage:
        ...

    async def get_notification(self, notification_id: UUID) -> Notification | None:
        ...

    async def list_unread_for_update(self, receiver_id: UUID) -> list[Notification]:
        ...

    async def count_unread(self, receiver_id: UUID) -> int:
        ...

    def add_many(self, notifications: Sequence[Notification]) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        ...

    async def refresh(self, notification: Notification) -> None:
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

    async def list_notifications(
        self,
        *,
        receiver_id: UUID,
        unread: bool | None,
        page: int,
        page_size: int,
    ) -> NotificationPage:
        conditions = [Notification.receiver_id == receiver_id]
        if unread is True:
            conditions.append(Notification.read_at.is_(None))
        elif unread is False:
            conditions.append(Notification.read_at.is_not(None))

        total = await self._session.scalar(
            select(func.count()).select_from(Notification).where(*conditions),
        )
        result = await self._session.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
        return NotificationPage(
            items=list(result.all()),
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )

    async def get_notification(self, notification_id: UUID) -> Notification | None:
        notification = await self._session.get(Notification, notification_id)
        return notification if isinstance(notification, Notification) else None

    async def list_unread_for_update(self, receiver_id: UUID) -> list[Notification]:
        result = await self._session.scalars(
            select(Notification)
            .where(Notification.receiver_id == receiver_id, Notification.read_at.is_(None))
            .with_for_update(),
        )
        return list(result.all())

    async def count_unread(self, receiver_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(Notification).where(
                Notification.receiver_id == receiver_id,
                Notification.read_at.is_(None),
            ),
        )
        return int(total or 0)

    def add_many(self, notifications: Sequence[Notification]) -> None:
        self._session.add_all(list(notifications))

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        for notification in notifications:
            await self._session.refresh(notification)

    async def refresh(self, notification: Notification) -> None:
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

    async def list_notifications(
        self,
        *,
        receiver_id: UUID,
        unread: bool | None,
        page: int,
        page_size: int,
    ) -> NotificationPage:
        notifications = [
            notification
            for notification in self.notifications
            if notification.receiver_id == receiver_id
        ]
        if unread is True:
            notifications = [
                notification for notification in notifications if notification.read_at is None
            ]
        elif unread is False:
            notifications = [
                notification
                for notification in notifications
                if notification.read_at is not None
            ]
        notifications = sorted(
            notifications,
            key=lambda notification: notification.created_at,
            reverse=True,
        )
        start = (page - 1) * page_size
        return NotificationPage(
            items=notifications[start : start + page_size],
            page=page,
            page_size=page_size,
            total=len(notifications),
        )

    async def get_notification(self, notification_id: UUID) -> Notification | None:
        return next(
            (
                notification
                for notification in self.notifications
                if notification.id == notification_id
            ),
            None,
        )

    async def list_unread_for_update(self, receiver_id: UUID) -> list[Notification]:
        return [
            notification
            for notification in self.notifications
            if notification.receiver_id == receiver_id and notification.read_at is None
        ]

    async def count_unread(self, receiver_id: UUID) -> int:
        return len(
            [
                notification
                for notification in self.notifications
                if notification.receiver_id == receiver_id and notification.read_at is None
            ],
        )

    def add_many(self, notifications: Sequence[Notification]) -> None:
        self.notifications.extend(notifications)

    async def commit(self) -> None:
        return None

    async def refresh_many(self, notifications: Sequence[Notification]) -> None:
        _ = notifications
        return None

    async def refresh(self, notification: Notification) -> None:
        _ = notification
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

    async def list_notifications(
        self,
        *,
        actor: User,
        unread: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> NotificationPage:
        self._validate_page(page=page, page_size=page_size)
        return await self._repository.list_notifications(
            receiver_id=actor.id,
            unread=unread,
            page=page,
            page_size=page_size,
        )

    async def unread_count(self, *, actor: User) -> int:
        return await self._repository.count_unread(actor.id)

    async def mark_read(self, *, actor: User, notification_id: UUID) -> Notification:
        notification = await self._get_owned_notification(
            actor=actor,
            notification_id=notification_id,
        )
        if notification.read_at is None:
            now = datetime.now(UTC)
            notification.read_at = now
            notification.updated_at = now
            await self._repository.commit()
            await self._repository.refresh(notification)
        return notification

    async def mark_all_read(self, *, actor: User) -> int:
        notifications = await self._repository.list_unread_for_update(actor.id)
        if not notifications:
            return 0
        now = datetime.now(UTC)
        for notification in notifications:
            notification.read_at = now
            notification.updated_at = now
        await self._repository.commit()
        await self._repository.refresh_many(notifications)
        return len(notifications)

    @staticmethod
    def build_dedup_key(
        *,
        scenario: str,
        receiver_id: UUID,
        source_id: str,
        business_date: date,
    ) -> str:
        return f"{scenario}:{receiver_id}:{source_id}:{business_date:%Y%m%d}"

    async def _get_owned_notification(
        self,
        *,
        actor: User,
        notification_id: UUID,
    ) -> Notification:
        notification = await self._repository.get_notification(notification_id)
        if notification is None or notification.receiver_id != actor.id:
            raise ResourceNotFoundError("Notification does not exist")
        return notification

    @staticmethod
    def _validate_page(*, page: int, page_size: int) -> None:
        if page < 1:
            raise ValidationFailedError("Page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValidationFailedError("Page size must be between 1 and 100")

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
