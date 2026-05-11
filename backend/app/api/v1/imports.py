from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.users import User
from app.schemas.imports import (
    ProjectImportCreatedProjectRead,
    ProjectImportResultRead,
    ProjectImportRowErrorRead,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.project_imports import (
    ProjectImportResult,
    ProjectImportService,
    SqlAlchemyProjectImportRepository,
)

router = APIRouter(prefix="/imports", tags=["imports"])


async def get_project_import_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectImportService:
    return ProjectImportService(repository=SqlAlchemyProjectImportRepository(session))


@router.get("/projects/template")
async def download_project_import_template(
    service: Annotated[ProjectImportService, Depends(get_project_import_service)],
    _current_user: Annotated[User, Depends(require_permission("project.import"))],
) -> Response:
    return Response(
        content=service.generate_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="project_import_template.xlsx"',
        },
    )


@router.post("/projects")
async def import_projects(
    file: Annotated[UploadFile, File()],
    background_tasks: BackgroundTasks,
    service: Annotated[ProjectImportService, Depends(get_project_import_service)],
    current_user: Annotated[User, Depends(require_permission("project.import"))],
) -> dict[str, object]:
    result = await service.import_projects(
        actor=current_user,
        content=await file.read(),
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_project_import_result(result))


def serialize_project_import_result(result: ProjectImportResult) -> dict[str, object]:
    payload = ProjectImportResultRead(
        batch_no=result.batch_no,
        total_rows=result.total_rows,
        success_count=result.success_count,
        failure_count=result.failure_count,
        duration_ms=result.duration_ms,
        errors=[
            ProjectImportRowErrorRead(
                row_number=error.row_number,
                field=error.field,
                message=error.message,
                value=error.value,
            )
            for error in result.errors
        ],
        created_projects=[
            ProjectImportCreatedProjectRead(
                id=project.id,
                project_no=project.project_no,
                name=project.name,
                dept_id=project.dept_id,
                status=project.status,
            )
            for project in result.created_projects
        ],
    )
    return payload.model_dump(mode="json")

