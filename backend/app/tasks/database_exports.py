from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.services.database_exports import (
    DatabaseExportService,
    NoopDatabaseExportTaskDispatcher,
    SqlAlchemyDatabaseExportRepository,
)
from app.storage.factory import create_storage_backend
from app.tasks.celery_app import celery_app
from app.tasks.task_names import DATABASE_EXPORT_TASK_NAME


async def run_database_export(job_id: UUID) -> dict[str, object]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = DatabaseExportService(
            repository=SqlAlchemyDatabaseExportRepository(session),
            storage=create_storage_backend(settings),
            dispatcher=NoopDatabaseExportTaskDispatcher(),
        )
        job = await service.run_export_job(job_id)
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "progress": job.progress,
            "table_count": job.table_count,
            "row_count": job.row_count,
        }


@celery_app.task(name=DATABASE_EXPORT_TASK_NAME)  # type: ignore[untyped-decorator]
def generate_database_export(job_id: str) -> dict[str, object]:
    return asyncio.run(run_database_export(UUID(job_id)))
