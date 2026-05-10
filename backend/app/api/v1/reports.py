from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.reports import ReportJob
from app.models.users import User
from app.schemas.reports import ReportCreate, ReportJobRead
from app.services.reports import ReportService, ReportTaskDispatcher, SqlAlchemyReportRepository
from app.storage.factory import create_storage_backend
from app.tasks.celery_app import celery_app
from app.tasks.task_names import REPORT_GENERATE_TASK_NAME

router = APIRouter(prefix="/reports", tags=["reports"])


class CeleryReportTaskDispatcher(ReportTaskDispatcher):
    def enqueue(self, job_id: UUID) -> None:
        celery_app.send_task(REPORT_GENERATE_TASK_NAME, args=[str(job_id)])


def get_report_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReportService:
    return ReportService(
        repository=SqlAlchemyReportRepository(session),
        storage=create_storage_backend(settings),
        dispatcher=CeleryReportTaskDispatcher(),
        async_threshold_rows=settings.report_async_threshold_rows,
    )


def serialize_report_job(job: ReportJob) -> dict[str, object]:
    available_formats: list[str] = []
    if job.xlsx_storage_key:
        available_formats.append("xlsx")
    if job.pdf_storage_key:
        available_formats.append("pdf")
    payload = ReportJobRead(
        id=job.id,
        report_type=job.report_type,
        requested_by_id=job.requested_by_id,
        parameters=job.parameters,
        status=job.status,
        progress=job.progress,
        row_count=job.row_count,
        available_formats=available_formats,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
    return payload.model_dump(mode="json")


@router.post("")
async def create_report(
    payload: ReportCreate,
    service: Annotated[ReportService, Depends(get_report_service)],
    current_user: Annotated[User, Depends(require_permission("report.generate"))],
) -> dict[str, object]:
    job = await service.create_report(actor=current_user, payload=payload)
    return success_response(serialize_report_job(job))


@router.get("/{job_id}")
async def get_report_job(
    job_id: UUID,
    service: Annotated[ReportService, Depends(get_report_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = await service.get_report_job(actor=current_user, job_id=job_id)
    return success_response(serialize_report_job(job))
