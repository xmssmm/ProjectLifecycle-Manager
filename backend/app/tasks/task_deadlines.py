from __future__ import annotations

import asyncio

from app.core.db import AsyncSessionLocal
from app.services.notification_runtime import build_notification_service
from app.services.task_deadlines import SqlAlchemyTaskDeadlineRepository, TaskDeadlineService
from app.tasks.celery_app import celery_app
from app.tasks.task_names import TASK_DEADLINE_SCAN_TASK_NAME


async def run_task_deadline_scan() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        service = TaskDeadlineService(
            repository=SqlAlchemyTaskDeadlineRepository(session),
            notification_service=build_notification_service(session=session),
        )
        result = await service.scan_deadlines_for_due_timezones()
        return result.to_dict()


@celery_app.task(name=TASK_DEADLINE_SCAN_TASK_NAME)  # type: ignore[untyped-decorator]
def scan_task_deadlines() -> dict[str, int]:
    return asyncio.run(run_task_deadline_scan())
