from __future__ import annotations

from email.message import EmailMessage
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.services.email_channel import (
    EmailNotificationChannel,
    InMemoryEmailRecipientResolver,
)
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


class RecordingEmailTransport:
    def __init__(self, *, success: bool = True, error: str | None = None) -> None:
        self.success = success
        self.error = error
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> ChannelDeliveryResult:
        self.messages.append(message)
        return ChannelDeliveryResult(
            channel=NotificationChannelType.email,
            success=self.success,
            error=self.error,
        )


def make_settings() -> Settings:
    return Settings(
        smtp_enabled=True,
        smtp_from_address="noreply@example.local",
        smtp_host="smtp.example.local",
        smtp_port=587,
    )


@pytest.mark.asyncio
async def test_email_channel_renders_task_due_today_template_with_payload_variables() -> None:
    receiver_id = uuid4()
    transport = RecordingEmailTransport()
    channel = EmailNotificationChannel(
        settings=make_settings(),
        recipient_resolver=InMemoryEmailRecipientResolver(
            {receiver_id: "member@example.local"},
        ),
        transport=transport,
    )

    result = await channel.send(
        NotificationChannelMessage(
            channel=NotificationChannelType.email,
            receiver_id=receiver_id,
            scenario="task_due_today",
            source_id="task-1",
            payload={
                "task_no": "T-001",
                "title": "提交验收材料",
                "due_date": "2026-05-10",
                "url": "https://pm.example.local/tasks/task-1",
            },
            dedup_key="task_due_today:user:task-1:20260510",
        ),
    )

    assert result.success is True
    assert len(transport.messages) == 1
    message = transport.messages[0]
    assert message["To"] == "member@example.local"
    assert message["From"] == "noreply@example.local"
    assert "T-001" in str(message["Subject"])
    body = message.get_content()
    assert "提交验收材料" in body
    assert "2026-05-10" in body
    assert "https://pm.example.local/tasks/task-1" in body


@pytest.mark.asyncio
async def test_email_channel_returns_transport_failure_result() -> None:
    receiver_id = uuid4()
    transport = RecordingEmailTransport(success=False, error="smtp rejected")
    channel = EmailNotificationChannel(
        settings=make_settings(),
        recipient_resolver=InMemoryEmailRecipientResolver(
            {receiver_id: "member@example.local"},
        ),
        transport=transport,
    )

    result = await channel.send(
        NotificationChannelMessage(
            channel=NotificationChannelType.email,
            receiver_id=receiver_id,
            scenario="project_pending_review",
            source_id="project-1",
            payload={"project_no": "P-001", "project_name": "数字化平台"},
            dedup_key="project_pending_review:user:project-1:20260510",
        ),
    )

    assert result.success is False
    assert result.error == "smtp rejected"
    assert len(transport.messages) == 1


@pytest.mark.asyncio
async def test_email_channel_unsubscribe_does_not_block_in_app_notification() -> None:
    receiver_id = UUID("00000000-0000-0000-0000-000000000123")
    transport = RecordingEmailTransport()
    email_channel = EmailNotificationChannel(
        settings=make_settings(),
        recipient_resolver=InMemoryEmailRecipientResolver(
            {receiver_id: "member@example.local"},
        ),
        transport=transport,
    )
    repository = InMemoryNotificationRepository(
        preferences={
            (receiver_id, "task_due_today"): StoredNotificationPreference(
                enabled=True,
                delivery_mode=NotificationDeliveryMode.real_time,
                channels={
                    NotificationChannelType.in_app: True,
                    NotificationChannelType.email: False,
                },
            ),
        },
    )
    service = NotificationService(
        repository=repository,
        channels={NotificationChannelType.email: email_channel},
    )

    sent = await service.send(
        scenario="task_due_today",
        receivers=[receiver_id],
        source_id="task-1",
        payload={"task_no": "T-001"},
    )

    assert len(sent) == 1
    assert repository.notifications == sent
    assert transport.messages == []
