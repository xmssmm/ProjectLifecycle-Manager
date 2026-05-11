from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.main_projects import MainProject
from app.models.users import User, UserRole
from app.schemas.archives import (
    ArchiveBatchDetailRead,
    ArchiveBatchListRead,
    ArchiveBatchRead,
    ArchiveCandidateRead,
    ArchiveMainProjectRead,
    ArchiveRunResultRead,
    ArchiveSubProjectRead,
)
from app.schemas.main_projects import MainProjectRead
from app.services.archives import (
    ArchiveBatchDetail,
    ArchiveBatchPage,
    ArchiveRunResult,
    ArchiveService,
    SqlAlchemyArchiveRepository,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context

router = APIRouter(prefix="/archives", tags=["archives"])


async def get_archive_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ArchiveService:
    return ArchiveService(repository=SqlAlchemyArchiveRepository(session))


def serialize_run_result(result: ArchiveRunResult) -> dict[str, object]:
    return ArchiveRunResultRead(
        batch_id=result.batch_id,
        batch_no=result.batch_no,
        archived_main_project_count=result.archived_main_project_count,
        archived_sub_project_count=result.archived_sub_project_count,
        main_projects_before=result.main_projects_before,
        main_projects_after=result.main_projects_after,
        duration_ms=result.duration_ms,
    ).model_dump(mode="json")


def serialize_batch_page(page: ArchiveBatchPage) -> dict[str, object]:
    return ArchiveBatchListRead(
        items=[ArchiveBatchRead.model_validate(batch) for batch in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
    ).model_dump(mode="json")


def serialize_batch_detail(detail: ArchiveBatchDetail) -> dict[str, object]:
    return ArchiveBatchDetailRead(
        batch=ArchiveBatchRead.model_validate(detail.batch),
        main_projects=[
            ArchiveMainProjectRead.model_validate(project) for project in detail.main_projects
        ],
        sub_projects=[
            ArchiveSubProjectRead.model_validate(project) for project in detail.sub_projects
        ],
    ).model_dump(mode="json")


def serialize_main_project(project: MainProject) -> dict[str, object]:
    return MainProjectRead.model_validate(project).model_dump(mode="json")


@router.get("/candidates")
async def list_archive_candidates(
    service: Annotated[ArchiveService, Depends(get_archive_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    candidates = await service.list_candidates()
    payload = [
        ArchiveCandidateRead(
            main_project_id=candidate.main_project_id,
            project_no=candidate.project_no,
            name=candidate.name,
            closed_at=candidate.closed_at,
            sub_project_count=candidate.sub_project_count,
        )
        for candidate in candidates
    ]
    return success_response([item.model_dump(mode="json") for item in payload])


@router.get("/batches")
async def list_archive_batches(
    service: Annotated[ArchiveService, Depends(get_archive_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    result = await service.list_batches(page=page, page_size=page_size)
    return success_response(serialize_batch_page(result))


@router.post("/batches")
async def create_archive_batch(
    background_tasks: BackgroundTasks,
    service: Annotated[ArchiveService, Depends(get_archive_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    result = await service.archive_eligible_projects(
        actor_id=current_user.id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_run_result(result))


@router.get("/batches/{batch_id}")
async def get_archive_batch(
    batch_id: UUID,
    service: Annotated[ArchiveService, Depends(get_archive_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    detail = await service.get_batch_detail(batch_id)
    return success_response(serialize_batch_detail(detail))


@router.post("/main-projects/{archive_main_project_id}/restore")
async def restore_archive_main_project(
    archive_main_project_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[ArchiveService, Depends(get_archive_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    project = await service.restore_main_project(
        actor=current_user,
        archive_main_project_id=archive_main_project_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_main_project(project))
