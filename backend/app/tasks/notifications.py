from __future__ import annotations

import asyncio

from app.core.db import AsyncSessionLocal
from app.services.notification_runtime import build_notification_service
from app.tasks.celery_app import celery_app
from app.tasks.task_names import NOTIFICATION_DIGEST_TASK_NAME


async def run_notification_digest() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        service = build_notification_service(session=session)
        result = await service.generate_daily_digest_for_due_timezones()
        return result.to_dict()


@celery_app.task(name=NOTIFICATION_DIGEST_TASK_NAME)  # type: ignore[untyped-decorator]
def generate_notification_digest() -> dict[str, int]:
    return asyncio.run(run_notification_digest())
