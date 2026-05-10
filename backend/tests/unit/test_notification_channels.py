from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.services.notification_channels import (
    ChannelDeliveryResult,
    NotificationChannelMessage,
    NotificationChannelType,
)
from app.services.notifications import (
    InMemoryNotificationRepository,
    NotificationDeliveryMode,
    NotificationService,
    StoredNotificationPreference,
)


class RecordingChannel:
    def __init__(self) -> None:
        self.messages: list[NotificationChannelMessage] = []

    async def send(self, message: NotificationChannelMessage) -> ChannelDeliveryResult:
        self.messages.append(message)
        return ChannelDeliveryResult(channel=message.channel, success=True)


@pytest.mark.asyncio
async def test_send_dispatches_enabled_external_channel_and_skips_disabled_channel() -> None:
    receiver_id = uuid4()
    source_id = uuid4()
    repository = InMemoryNotificationRepository(
        preferences={
            (receiver_id, "task_assigned"): StoredNotificationPreference(
                enabled=True,
                delivery_mode=NotificationDeliveryMode.real_time,
                channels={
                    NotificationChannelType.in_app: True,
                    NotificationChannelType.email: True,
                    NotificationChannelType.wework: False,
                },
            ),
        },
    )
    email_channel = RecordingChannel()
    wework_channel = RecordingChannel()
    service = NotificationService(
        repository=repository,
        business_date_provider=lambda: date(2026, 5, 10),
        channels={
            NotificationChannelType.email: email_channel,
            NotificationChannelType.wework: wework_channel,
        },
    )

    sent = await service.send(
        scenario="task_assigned",
        receivers=[receiver_id],
        source_id=source_id,
        payload={"task_no": "T-001"},
    )

    assert len(sent) == 1
    assert len(email_channel.messages) == 1
    assert email_channel.messages[0].channel == NotificationChannelType.email
    assert email_channel.messages[0].receiver_id == receiver_id
    assert email_channel.messages[0].dedup_key == sent[0].dedup_key
    assert email_channel.messages[0].payload == {"task_no": "T-001"}
    assert wework_channel.messages == []


@pytest.mark.asyncio
async def test_send_can_disable_in_app_channel_without_blocking_external_channel() -> None:
    receiver_id = uuid4()
    repository = InMemoryNotificationRepository(
        preferences={
            (receiver_id, "project_pending_review"): StoredNotificationPreference(
                enabled=False,
                delivery_mode=NotificationDeliveryMode.real_time,
                channels={
                    NotificationChannelType.in_app: False,
                    NotificationChannelType.email: True,
                },
            ),
        },
    )
    email_channel = RecordingChannel()
    service = NotificationService(
        repository=repository,
        business_date_provider=lambda: date(2026, 5, 10),
        channels={NotificationChannelType.email: email_channel},
    )

    sent = await service.send(
        scenario="project_pending_review",
        receivers=[receiver_id],
        source_id=uuid4(),
        payload={"project_no": "P-001"},
    )

    assert sent == []
    assert repository.notifications == []
    assert len(email_channel.messages) == 1
