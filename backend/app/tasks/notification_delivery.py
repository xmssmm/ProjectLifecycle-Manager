from __future__ import annotations

import asyncio

from app.core.db import AsyncSessionLocal
from app.services.notification_deliveries import (
    NotificationDeliveryService,
    SqlAlchemyNotificationDeliveryRepository,
)
from app.services.notification_runtime import build_external_notification_channels
from app.tasks.celery_app import celery_app
from app.tasks.task_names import NOTIFICATION_DELIVERY_RETRY_TASK_NAME


async def run_notification_delivery_retry(limit: int = 100) -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        service = NotificationDeliveryService(
            repository=SqlAlchemyNotificationDeliveryRepository(session),
        )
        return await service.process_due(
            channels=build_external_notification_channels(session=session),
            limit=limit,
        )


@celery_app.task(name=NOTIFICATION_DELIVERY_RETRY_TASK_NAME)  # type: ignore[untyped-decorator]
def retry_notification_deliveries(limit: int = 100) -> dict[str, int]:
    return asyncio.run(run_notification_delivery_retry(limit=limit))
