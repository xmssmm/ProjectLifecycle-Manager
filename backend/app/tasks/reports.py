from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.services.reports import NoopReportTaskDispatcher, ReportService, SqlAlchemyReportRepository
from app.storage.factory import create_storage_backend
from app.tasks.celery_app import celery_app
from app.tasks.task_names import REPORT_CLEANUP_TASK_NAME, REPORT_GENERATE_TASK_NAME


async def run_report_generation(job_id: UUID) -> dict[str, object]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = ReportService(
            repository=SqlAlchemyReportRepository(session),
            storage=create_storage_backend(settings),
            dispatcher=NoopReportTaskDispatcher(),
            async_threshold_rows=settings.report_async_threshold_rows,
        )
        job = await service.run_report_job(job_id)
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "progress": job.progress,
            "row_count": job.row_count,
        }


@celery_app.task(name=REPORT_GENERATE_TASK_NAME)  # type: ignore[untyped-decorator]
def generate_report(job_id: str) -> dict[str, object]:
    return asyncio.run(run_report_generation(UUID(job_id)))


async def run_report_cleanup(*, retention_days: int = 7) -> dict[str, int]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = ReportService(
            repository=SqlAlchemyReportRepository(session),
            storage=create_storage_backend(settings),
            dispatcher=NoopReportTaskDispatcher(),
            async_threshold_rows=settings.report_async_threshold_rows,
        )
        result = await service.cleanup_expired_reports(retention_days=retention_days)
        return {
            "deleted_jobs": result.deleted_jobs,
            "deleted_files": result.deleted_files,
        }


@celery_app.task(name=REPORT_CLEANUP_TASK_NAME)  # type: ignore[untyped-decorator]
def cleanup_expired_reports(retention_days: int = 7) -> dict[str, int]:
    return asyncio.run(run_report_cleanup(retention_days=retention_days))
