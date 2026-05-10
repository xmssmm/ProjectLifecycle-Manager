from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_permission, require_role
from app.core.responses import success_response
from app.models.main_projects import MainProject
from app.models.users import User, UserRole
from app.schemas.main_projects import (
    MainProjectCreate,
    MainProjectListRead,
    MainProjectRead,
    MainProjectReviewRequest,
    MainProjectUpdate,
    ProjectProgressFunnelItemRead,
    ProjectProgressFunnelRead,
    ProjectProgressFunnelSubProjectRead,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.main_projects import (
    MainProjectService,
    ProjectProgressFunnel,
    SqlAlchemyMainProjectRepository,
)
from app.services.notifications import NotificationService, SqlAlchemyNotificationRepository

router = APIRouter(prefix="/main-projects", tags=["main-projects"])


async def get_main_project_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MainProjectService:
    return MainProjectService(
        repository=SqlAlchemyMainProjectRepository(session),
        notification_service=NotificationService(
            repository=SqlAlchemyNotificationRepository(session),
        ),
    )


def serialize_main_project(project: MainProject) -> dict[str, object]:
    return MainProjectRead.model_validate(project).model_dump(mode="json")


def serialize_progress_funnel(funnel: ProjectProgressFunnel) -> dict[str, object]:
    payload = ProjectProgressFunnelRead(
        main_project_id=funnel.main_project_id,
        total_sub_projects=funnel.total_sub_projects,
        items=[
            ProjectProgressFunnelItemRead(
                phase_no=item.phase_no,
                code=item.code,
                name=item.name,
                sub_project_count=item.sub_project_count,
                sub_projects=[
                    ProjectProgressFunnelSubProjectRead(
                        id=sub_project.id,
                        project_no=sub_project.project_no,
                        name=sub_project.name,
                        status=sub_project.status,
                        phase_status=sub_project.phase_status,
                    )
                    for sub_project in item.sub_projects
                ],
            )
            for item in funnel.items
        ],
    )
    return payload.model_dump(mode="json")


@router.get("")
async def list_main_projects(
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(require_permission("project.view_all"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    projects, total = await service.list_projects(
        actor=current_user,
        page=page,
        page_size=page_size,
    )
    payload = MainProjectListRead(
        items=[MainProjectRead.model_validate(project) for project in projects],
        total=total,
        page=page,
        page_size=page_size,
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def create_main_project(
    payload: MainProjectCreate,
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.dept_manager))],
) -> dict[str, object]:
    project = await service.create_project(actor=current_user, payload=payload)
    return success_response(serialize_main_project(project))


@router.get("/{project_id}")
async def get_main_project(
    project_id: UUID,
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(require_permission("project.view_all"))],
) -> dict[str, object]:
    project = await service.get_project(actor=current_user, project_id=project_id)
    return success_response(serialize_main_project(project))


@router.get("/{project_id}/progress-funnel")
async def get_project_progress_funnel(
    project_id: UUID,
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    funnel = await service.get_progress_funnel(actor=current_user, project_id=project_id)
    return success_response(serialize_progress_funnel(funnel))


@router.put("/{project_id}")
async def update_main_project(
    project_id: UUID,
    payload: MainProjectUpdate,
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = await service.update_project(
        actor=current_user,
        project_id=project_id,
        payload=payload,
    )
    return success_response(serialize_main_project(project))


@router.post("/{project_id}/submit")
async def submit_main_project(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = await service.submit_project(
        actor=current_user,
        project_id=project_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_main_project(project))


@router.post("/{project_id}/review")
async def review_main_project(
    project_id: UUID,
    payload: MainProjectReviewRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = await service.review_project(
        actor=current_user,
        project_id=project_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_main_project(project))


@router.post("/{project_id}/close")
async def close_main_project(
    project_id: UUID,
    service: Annotated[MainProjectService, Depends(get_main_project_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.dept_manager))],
) -> dict[str, object]:
    project = await service.close_project(actor=current_user, project_id=project_id)
    return success_response(serialize_main_project(project))
