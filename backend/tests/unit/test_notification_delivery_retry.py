from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.notification_deliveries import NotificationDeliveryStatus
from app.services.notification_channels import (
    ChannelDeliveryResult,
    NotificationChannelMessage,
    NotificationChannelType,
)
from app.services.notification_deliveries import (
    InMemoryNotificationDeliveryRepository,
    NotificationDeliveryService,
)
from app.services.notifications import (
    InMemoryNotificationRepository,
    NotificationDeliveryMode,
    NotificationService,
    StoredNotificationPreference,
)


class SequencedChannel:
    def __init__(self, results: list[ChannelDeliveryResult]) -> None:
        self.results = results
        self.messages: list[NotificationChannelMessage] = []

    async def send(self, message: NotificationChannelMessage) -> ChannelDeliveryResult:
        self.messages.append(message)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_external_delivery_failure_increments_attempt_and_schedules_retry() -> None:
    now = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)
    receiver_id = uuid4()
    notification_repository = InMemoryNotificationRepository(
        preferences={
            (receiver_id, "task_due_today"): StoredNotificationPreference(
                enabled=False,
                delivery_mode=NotificationDeliveryMode.real_time,
                channels={
                    NotificationChannelType.in_app: False,
                    NotificationChannelType.email: True,
                },
            ),
        },
    )
    delivery_repository = InMemoryNotificationDeliveryRepository()
    delivery_service = NotificationDeliveryService(
        repository=delivery_repository,
        now_provider=lambda: now,
    )
    email_channel = SequencedChannel(
        [
            ChannelDeliveryResult(
                channel=NotificationChannelType.email,
                success=False,
                error="smtp down",
            ),
        ],
    )
    service = NotificationService(
        repository=notification_repository,
        business_date_provider=lambda: date(2026, 5, 10),
        delivery_service=delivery_service,
        channels={NotificationChannelType.email: email_channel},
    )

    sent = await service.send(
        scenario="task_due_today",
        receivers=[receiver_id],
        source_id="task-1",
        payload={"task_no": "T-001"},
    )

    assert sent == []
    assert len(delivery_repository.deliveries) == 1
    delivery = delivery_repository.deliveries[0]
    assert delivery.channel == NotificationChannelType.email
    assert delivery.scenario == "task_due_today"
    assert delivery.receiver_id == receiver_id
    assert delivery.attempt_count == 1
    assert delivery.status == NotificationDeliveryStatus.retry_scheduled
    assert delivery.last_error == "smtp down"
    assert delivery.next_retry_at == now + timedelta(minutes=1)
    assert len(email_channel.messages) == 1


@pytest.mark.asyncio
async def test_retry_reaches_dead_letter_and_notifies_admin() -> None:
    now = datetime(2026, 5, 10, 9, 5, tzinfo=UTC)
    admin_id = uuid4()
    receiver_id = uuid4()
    delivery_repository = InMemoryNotificationDeliveryRepository(admin_user_ids=[admin_id])
    delivery = delivery_repository.create_delivery(
        NotificationChannelMessage(
            channel=NotificationChannelType.wework,
            receiver_id=receiver_id,
            scenario="project_pending_review",
            source_id="project-1",
            payload={"project_no": "P-001"},
            dedup_key="project_pending_review:user:project-1:20260510",
        ),
        now=now - timedelta(minutes=1),
    )
    delivery.attempt_count = 2
    delivery.status = NotificationDeliveryStatus.retry_scheduled
    delivery.next_retry_at = now
    channel = SequencedChannel(
        [
            ChannelDeliveryResult(
                channel=NotificationChannelType.wework,
                success=False,
                error="webhook 500",
            ),
        ],
    )
    service = NotificationDeliveryService(
        repository=delivery_repository,
        now_provider=lambda: now,
    )

    result = await service.process_due(
        channels={NotificationChannelType.wework: channel},
    )

    assert result == {"processed": 1, "delivered": 0, "retry_scheduled": 0, "dead_letter": 1}
    assert delivery.attempt_count == 3
    assert delivery.status == NotificationDeliveryStatus.dead_letter
    assert delivery.last_error == "webhook 500"
    assert delivery.next_retry_at is None
    assert len(delivery_repository.admin_notifications) == 1
    admin_notification = delivery_repository.admin_notifications[0]
    assert admin_notification.receiver_id == admin_id
    assert admin_notification.scenario == "notification_delivery_dead_letter"
    assert admin_notification.payload["delivery_id"] == str(delivery.id)


@pytest.mark.asyncio
async def test_retry_success_marks_delivery_delivered() -> None:
    now = datetime(2026, 5, 10, 9, 10, tzinfo=UTC)
    delivery_repository = InMemoryNotificationDeliveryRepository()
    delivery = delivery_repository.create_delivery(
        NotificationChannelMessage(
            channel=NotificationChannelType.dingtalk,
            receiver_id=uuid4(),
            scenario="task_due_today",
            source_id="task-1",
            payload={"task_no": "T-001"},
            dedup_key="task_due_today:user:task-1:20260510",
        ),
        now=now - timedelta(minutes=1),
    )
    channel = SequencedChannel(
        [
            ChannelDeliveryResult(
                channel=NotificationChannelType.dingtalk,
                success=True,
            ),
        ],
    )
    service = NotificationDeliveryService(
        repository=delivery_repository,
        now_provider=lambda: now,
    )

    result = await service.process_due(
        channels={NotificationChannelType.dingtalk: channel},
    )

    assert result == {"processed": 1, "delivered": 1, "retry_scheduled": 0, "dead_letter": 0}
    assert delivery.attempt_count == 1
    assert delivery.status == NotificationDeliveryStatus.delivered
    assert delivery.delivered_at == now
    assert delivery.next_retry_at is None
    assert delivery.last_error is None


def test_celery_beat_schedules_notification_delivery_retry_every_minute() -> None:
    from app.tasks.celery_app import create_celery_app
    from app.tasks.task_names import NOTIFICATION_DELIVERY_RETRY_TASK_NAME

    celery_app = create_celery_app()

    schedule = celery_app.conf.beat_schedule["notification-delivery-retry-every-minute"]
    assert schedule["task"] == NOTIFICATION_DELIVERY_RETRY_TASK_NAME
    assert schedule["schedule"] == 60.0
