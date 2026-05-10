from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.services.notification_runtime import build_notification_service
from app.services.virus_scan import (
    ClamAvVirusScanner,
    DocumentScanService,
    SqlAlchemyDocumentScanRepository,
)
from app.storage.factory import create_storage_backend
from app.tasks.celery_app import celery_app
from app.tasks.task_names import DOCUMENT_SCAN_TASK_NAME


class CeleryDocumentScanScheduler:
    def enqueue(self, document_id: UUID) -> None:
        scan_document_file.delay(str(document_id))


async def run_document_scan(document_id: UUID) -> dict[str, str]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = DocumentScanService(
            repository=SqlAlchemyDocumentScanRepository(session),
            storage=create_storage_backend(settings),
            scanner=ClamAvVirusScanner(
                host=settings.clamav_host,
                port=settings.clamav_port,
                timeout_seconds=settings.clamav_timeout_seconds,
            ),
            notification_service=build_notification_service(session=session, settings=settings),
        )
        result = await service.scan_document(document_id)
        return {
            "document_id": str(result.document_id),
            "status": result.status.value,
            "result": result.result,
        }


@celery_app.task(name=DOCUMENT_SCAN_TASK_NAME)  # type: ignore[untyped-decorator]
def scan_document_file(document_id: str) -> dict[str, str]:
    return asyncio.run(run_document_scan(UUID(document_id)))
