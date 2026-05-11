from __future__ import annotations

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import AsyncSessionLocal, get_db_session
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.exports import DatabaseExportJob
from app.models.users import User
from app.schemas.exports import DatabaseExportJobRead
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.database_exports import (
    DatabaseExportDownload,
    DatabaseExportService,
    DatabaseExportTaskDispatcher,
    SqlAlchemyDatabaseExportRepository,
)
from app.storage.factory import create_storage_backend
from app.tasks.celery_app import celery_app
from app.tasks.task_names import DATABASE_EXPORT_TASK_NAME

router = APIRouter(prefix="/exports", tags=["exports"])


class CeleryDatabaseExportTaskDispatcher(DatabaseExportTaskDispatcher):
    def enqueue(self, job_id: UUID) -> None:
        celery_app.send_task(DATABASE_EXPORT_TASK_NAME, args=[str(job_id)])


def get_database_export_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatabaseExportService:
    return DatabaseExportService(
        repository=SqlAlchemyDatabaseExportRepository(session),
        storage=create_storage_backend(settings),
        dispatcher=CeleryDatabaseExportTaskDispatcher(),
    )


@router.post("/database")
async def create_database_export(
    background_tasks: BackgroundTasks,
    service: Annotated[DatabaseExportService, Depends(get_database_export_service)],
    current_user: Annotated[User, Depends(require_permission("database.export"))],
) -> dict[str, object]:
    job = await service.create_export(
        actor=current_user,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_database_export_job(job))


@router.get("/database/{job_id}")
async def get_database_export_job(
    job_id: UUID,
    service: Annotated[DatabaseExportService, Depends(get_database_export_service)],
    current_user: Annotated[User, Depends(require_permission("database.export"))],
) -> dict[str, object]:
    job = await service.get_export_job(actor=current_user, job_id=job_id)
    return success_response(serialize_database_export_job(job))


@router.get("/database/{job_id}/download")
async def download_database_export(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[DatabaseExportService, Depends(get_database_export_service)],
    current_user: Annotated[User, Depends(require_permission("database.export"))],
) -> StreamingResponse:
    download = await service.download_export(
        actor=current_user,
        job_id=job_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return streaming_zip_response(download)


def serialize_database_export_job(job: DatabaseExportJob) -> dict[str, object]:
    download_url = (
        f"/api/v1/exports/database/{job.id}/download" if job.storage_key is not None else None
    )
    payload = DatabaseExportJobRead(
        id=job.id,
        requested_by_id=job.requested_by_id,
        status=job.status,
        progress=job.progress,
        table_count=job.table_count,
        row_count=job.row_count,
        download_url=download_url,
        manifest=job.manifest,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
    return payload.model_dump(mode="json")


def streaming_zip_response(download: DatabaseExportDownload) -> StreamingResponse:
    encoded_filename = quote(download.file_name)
    return StreamingResponse(
        iter([download.content]),
        media_type=download.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{encoded_filename}; "
                f'filename="{download.file_name}"'
            ),
        },
    )
