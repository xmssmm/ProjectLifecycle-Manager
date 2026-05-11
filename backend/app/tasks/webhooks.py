from __future__ import annotations

import asyncio

from app.core.db import AsyncSessionLocal
from app.services.webhooks import (
    SqlAlchemyWebhookRepository,
    WebhookService,
)
from app.tasks.celery_app import celery_app
from app.tasks.task_names import WEBHOOK_DELIVERY_RETRY_TASK_NAME


async def process_webhook_deliveries(
    *,
    service: WebhookService,
    limit: int,
) -> dict[str, int]:
    return await service.process_due(limit=limit)


async def run_webhook_delivery_retry(limit: int = 100) -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        service = WebhookService(repository=SqlAlchemyWebhookRepository(session))
        return await process_webhook_deliveries(service=service, limit=limit)


@celery_app.task(name=WEBHOOK_DELIVERY_RETRY_TASK_NAME)  # type: ignore[untyped-decorator]
def retry_webhook_deliveries(limit: int = 100) -> dict[str, int]:
    return asyncio.run(run_webhook_delivery_retry(limit=limit))
