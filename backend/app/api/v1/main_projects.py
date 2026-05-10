from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_permission, require_role
from app.core.responses import success_response
from app.models.main_projects import MainProject
from app.models.users import User, UserRole
from app.schemas.main_projects import (
    MainProjectCreate,
    MainProjectListRead,
    MainProjectRead,
    MainProjectUpdate,
)
from app.services.main_projects import MainProjectService, SqlAlchemyMainProjectRepository

router = APIRouter(prefix="/main-projects", tags=["main-projects"])


async def get_main_project_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MainProjectService:
    return MainProjectService(repository=SqlAlchemyMainProjectRepository(session))


def serialize_main_project(project: MainProject) -> dict[str, object]:
    return MainProjectRead.model_validate(project).model_dump(mode="json")


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
