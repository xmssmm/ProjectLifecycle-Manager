from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.services.custom_reports import (
    CustomReportService,
    NotificationServiceCustomReportSender,
    SqlAlchemyCustomReportQueryExecutor,
    SqlAlchemyCustomReportRepository,
)
from app.services.notification_runtime import build_notification_service
from app.storage.factory import create_storage_backend
from app.tasks.celery_app import celery_app
from app.tasks.task_names import CUSTOM_REPORT_SCHEDULE_SCAN_TASK_NAME


async def run_scheduled_custom_report_scan() -> dict[str, int]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = CustomReportService(
            repository=SqlAlchemyCustomReportRepository(session),
            query_executor=SqlAlchemyCustomReportQueryExecutor(session),
            storage=create_storage_backend(settings),
            notification_sender=NotificationServiceCustomReportSender(
                build_notification_service(session=session, settings=settings),
            ),
        )
        result = await service.run_due_scheduled_reports()
        return result.to_dict()


@celery_app.task(name=CUSTOM_REPORT_SCHEDULE_SCAN_TASK_NAME)  # type: ignore[untyped-decorator]
def scan_scheduled_custom_reports() -> dict[str, int]:
    return asyncio.run(run_scheduled_custom_report_scan())
