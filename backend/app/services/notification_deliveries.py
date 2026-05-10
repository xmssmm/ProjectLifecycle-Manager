from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_deliveries import (
    NotificationDelivery,
    NotificationDeliveryStatus,
)
from app.models.notifications import Notification
from app.models.users import User, UserRole, UserStatus
from app.services.notification_channels import (
    ChannelDeliveryResult,
    NotificationChannel,
    NotificationChannelMessage,
    NotificationChannelType,
)

DEAD_LETTER_SCENARIO = "notification_delivery_dead_letter"
DEFAULT_NOTIFICATION_MAX_ATTEMPTS = 3
DEFAULT_NOTIFICATION_RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5))


def current_utc_datetime() -> datetime:
    return datetime.now(UTC)


class NotificationDeliveryRepository(Protocol):
    def add_delivery(self, delivery: NotificationDelivery) -> None:
        ...

    async def list_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[NotificationDelivery]:
        ...

    async def admin_user_ids(self) -> list[UUID]:
        ...

    def add_admin_notifications(self, notifications: Sequence[Notification]) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh(self, delivery: NotificationDelivery) -> None:
        ...


class SqlAlchemyNotificationDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_delivery(self, delivery: NotificationDelivery) -> None:
        self._session.add(delivery)

    async def list_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[NotificationDelivery]:
        result = await self._session.scalars(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.status.in_(
                    [
                        NotificationDeliveryStatus.pending,
                        NotificationDeliveryStatus.retry_scheduled,
                    ],
                ),
                NotificationDelivery.next_retry_at <= now,
            )
            .order_by(NotificationDelivery.next_retry_at, NotificationDelivery.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True),
        )
        return list(result.all())

    async def admin_user_ids(self) -> list[UUID]:
        result = await self._session.scalars(
            select(User.id).where(
                User.role == UserRole.admin,
                User.status == UserStatus.active,
            ),
        )
        return list(result.all())

    def add_admin_notifications(self, notifications: Sequence[Notification]) -> None:
        self._session.add_all(list(notifications))

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, delivery: NotificationDelivery) -> None:
        await self._session.refresh(delivery)


class InMemoryNotificationDeliveryRepository:
    def __init__(
        self,
        deliveries: Sequence[NotificationDelivery] | None = None,
        admin_user_ids: Sequence[UUID] | None = None,
    ) -> None:
        self.deliveries = list(deliveries or [])
        self._admin_user_ids = list(admin_user_ids or [])
        self.admin_notifications: list[Notification] = []

    def create_delivery(
        self,
        message: NotificationChannelMessage,
        *,
        now: datetime,
    ) -> NotificationDelivery:
        delivery = build_notification_delivery(message, now=now)
        self.add_delivery(delivery)
        return delivery

    def add_delivery(self, delivery: NotificationDelivery) -> None:
        self.deliveries.append(delivery)

    async def list_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[NotificationDelivery]:
        due = [
            delivery
            for delivery in self.deliveries
            if delivery.status
            in {
                NotificationDeliveryStatus.pending,
                NotificationDeliveryStatus.retry_scheduled,
            }
            and delivery.next_retry_at is not None
            and delivery.next_retry_at <= now
        ]
        return sorted(due, key=lambda item: (item.next_retry_at, item.created_at))[:limit]

    async def admin_user_ids(self) -> list[UUID]:
        return list(self._admin_user_ids)

    def add_admin_notifications(self, notifications: Sequence[Notification]) -> None:
        self.admin_notifications.extend(notifications)

    async def commit(self) -> None:
        return None

    async def refresh(self, delivery: NotificationDelivery) -> None:
        _ = delivery
        return None


class NotificationDeliveryService:
    def __init__(
        self,
        *,
        repository: NotificationDeliveryRepository,
        now_provider: Callable[[], datetime] = current_utc_datetime,
        retry_delays: Sequence[timedelta] = DEFAULT_NOTIFICATION_RETRY_DELAYS,
        max_attempts: int = DEFAULT_NOTIFICATION_MAX_ATTEMPTS,
    ) -> None:
        self._repository = repository
        self._now_provider = now_provider
        self._retry_delays = tuple(retry_delays)
        self._max_attempts = max_attempts

    async def enqueue_and_attempt(
        self,
        *,
        message: NotificationChannelMessage,
        channel: NotificationChannel,
    ) -> NotificationDelivery:
        now = self._now_provider()
        delivery = build_notification_delivery(
            message,
            now=now,
            max_attempts=self._max_attempts,
        )
        self._repository.add_delivery(delivery)
        await self._repository.commit()
        await self._repository.refresh(delivery)
        await self.attempt_delivery(delivery=delivery, channel=channel)
        return delivery

    async def process_due(
        self,
        *,
        channels: Mapping[NotificationChannelType, NotificationChannel],
        limit: int = 100,
    ) -> dict[str, int]:
        now = self._now_provider()
        deliveries = await self._repository.list_due_deliveries(now=now, limit=limit)
        result = {"processed": 0, "delivered": 0, "retry_scheduled": 0, "dead_letter": 0}
        for delivery in deliveries:
            channel_type = NotificationChannelType(delivery.channel)
            channel = channels.get(channel_type)
            if channel is None:
                await self.mark_failed_attempt(
                    delivery=delivery,
                    error=f"{channel_type.value} channel is not configured",
                )
            else:
                await self.attempt_delivery(delivery=delivery, channel=channel)
            result["processed"] += 1
            if delivery.status == NotificationDeliveryStatus.delivered:
                result["delivered"] += 1
            elif delivery.status == NotificationDeliveryStatus.retry_scheduled:
                result["retry_scheduled"] += 1
            elif delivery.status == NotificationDeliveryStatus.dead_letter:
                result["dead_letter"] += 1
        return result

    async def attempt_delivery(
        self,
        *,
        delivery: NotificationDelivery,
        channel: NotificationChannel,
    ) -> None:
        if delivery.status in {
            NotificationDeliveryStatus.delivered,
            NotificationDeliveryStatus.dead_letter,
        }:
            return

        message = self._message_from_delivery(delivery)
        try:
            result = await channel.send(message)
        except TimeoutError:
            result = ChannelDeliveryResult(
                channel=message.channel,
                success=False,
                error="request timed out",
            )
        except Exception as exc:  # noqa: BLE001
            result = ChannelDeliveryResult(
                channel=message.channel,
                success=False,
                error=str(exc),
            )

        if result.success:
            await self.mark_delivered(delivery=delivery)
            return
        await self.mark_failed_attempt(
            delivery=delivery,
            error=result.error or "channel returned failure",
        )

    async def mark_delivered(self, *, delivery: NotificationDelivery) -> None:
        now = self._now_provider()
        delivery.attempt_count += 1
        delivery.status = NotificationDeliveryStatus.delivered
        delivery.last_error = None
        delivery.next_retry_at = None
        delivery.last_attempt_at = now
        delivery.delivered_at = now
        delivery.updated_at = now
        await self._repository.commit()

    async def mark_failed_attempt(self, *, delivery: NotificationDelivery, error: str) -> None:
        now = self._now_provider()
        delivery.attempt_count += 1
        delivery.last_error = error
        delivery.last_attempt_at = now
        delivery.delivered_at = None
        delivery.updated_at = now

        if delivery.attempt_count >= delivery.max_attempts:
            delivery.status = NotificationDeliveryStatus.dead_letter
            delivery.next_retry_at = None
            await self._notify_admins(delivery=delivery, now=now)
        else:
            delivery.status = NotificationDeliveryStatus.retry_scheduled
            delivery.next_retry_at = self._next_retry_at(
                now=now,
                attempt_count=delivery.attempt_count,
            )
        await self._repository.commit()

    def _next_retry_at(self, *, now: datetime, attempt_count: int) -> datetime:
        if not self._retry_delays:
            return now
        delay_index = min(attempt_count - 1, len(self._retry_delays) - 1)
        return now + self._retry_delays[delay_index]

    async def _notify_admins(self, *, delivery: NotificationDelivery, now: datetime) -> None:
        admin_user_ids = await self._repository.admin_user_ids()
        notifications = [
            Notification(
                id=uuid4(),
                receiver_id=admin_id,
                scenario=DEAD_LETTER_SCENARIO,
                source_id=str(delivery.id),
                payload={
                    "delivery_id": str(delivery.id),
                    "channel": delivery.channel,
                    "scenario": delivery.scenario,
                    "receiver_id": str(delivery.receiver_id),
                    "last_error": delivery.last_error,
                    "attempt_count": delivery.attempt_count,
                },
                dedup_key=f"{DEAD_LETTER_SCENARIO}:{admin_id}:{delivery.id}",
                delivery_mode="real_time",
                digest_sent_at=None,
                read_at=None,
                created_at=now,
                updated_at=now,
            )
            for admin_id in admin_user_ids
        ]
        if notifications:
            self._repository.add_admin_notifications(notifications)

    @staticmethod
    def _message_from_delivery(delivery: NotificationDelivery) -> NotificationChannelMessage:
        return NotificationChannelMessage(
            channel=NotificationChannelType(delivery.channel),
            receiver_id=delivery.receiver_id,
            scenario=delivery.scenario,
            source_id=delivery.source_id,
            payload=dict(delivery.payload),
            dedup_key=delivery.dedup_key,
        )


def build_notification_delivery(
    message: NotificationChannelMessage,
    *,
    now: datetime,
    max_attempts: int = DEFAULT_NOTIFICATION_MAX_ATTEMPTS,
) -> NotificationDelivery:
    return NotificationDelivery(
        id=uuid4(),
        channel=message.channel.value,
        scenario=message.scenario,
        receiver_id=message.receiver_id,
        source_id=message.source_id,
        payload=dict(message.payload),
        dedup_key=message.dedup_key,
        status=NotificationDeliveryStatus.pending,
        attempt_count=0,
        max_attempts=max_attempts,
        last_error=None,
        next_retry_at=now,
        last_attempt_at=None,
        delivered_at=None,
        created_at=now,
        updated_at=now,
    )
