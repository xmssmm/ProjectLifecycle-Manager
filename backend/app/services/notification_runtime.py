from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.services.dingtalk_channel import DingTalkNotificationChannel
from app.services.email_channel import EmailNotificationChannel, SqlAlchemyEmailRecipientResolver
from app.services.notification_channels import NotificationChannel, NotificationChannelType
from app.services.notification_deliveries import (
    NotificationDeliveryService,
    SqlAlchemyNotificationDeliveryRepository,
)
from app.services.notifications import NotificationService, SqlAlchemyNotificationRepository
from app.services.wework_channel import WeworkNotificationChannel


def build_external_notification_channels(
    *,
    session: AsyncSession,
    settings: Settings | None = None,
) -> dict[NotificationChannelType, NotificationChannel]:
    resolved_settings = settings or get_settings()
    return {
        NotificationChannelType.email: EmailNotificationChannel(
            settings=resolved_settings,
            recipient_resolver=SqlAlchemyEmailRecipientResolver(session),
        ),
        NotificationChannelType.wework: WeworkNotificationChannel(settings=resolved_settings),
        NotificationChannelType.dingtalk: DingTalkNotificationChannel(settings=resolved_settings),
    }


def build_notification_service(
    *,
    session: AsyncSession,
    settings: Settings | None = None,
) -> NotificationService:
    resolved_settings = settings or get_settings()
    return NotificationService(
        repository=SqlAlchemyNotificationRepository(session),
        channels=build_external_notification_channels(
            session=session,
            settings=resolved_settings,
        ),
        delivery_service=NotificationDeliveryService(
            repository=SqlAlchemyNotificationDeliveryRepository(session),
        ),
    )
