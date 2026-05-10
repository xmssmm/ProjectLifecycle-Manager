from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.sub_projects import SubProject
from app.models.users import User, UserRole
from app.schemas.sub_projects import (
    SubProjectCreate,
    SubProjectListRead,
    SubProjectRead,
    SubProjectUpdate,
)
from app.services.sub_projects import SqlAlchemySubProjectRepository, SubProjectService

router = APIRouter(prefix="/sub-projects", tags=["sub-projects"])


async def get_sub_project_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubProjectService:
    return SubProjectService(repository=SqlAlchemySubProjectRepository(session))


def serialize_sub_project(sub_project: SubProject) -> dict[str, object]:
    return SubProjectRead.model_validate(sub_project).model_dump(mode="json")


@router.get("")
async def list_sub_projects(
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    sub_projects, total = await service.list_sub_projects(
        actor=current_user,
        page=page,
        page_size=page_size,
    )
    payload = SubProjectListRead(
        items=[SubProjectRead.model_validate(sub_project) for sub_project in sub_projects],
        total=total,
        page=page,
        page_size=page_size,
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def create_sub_project(
    payload: SubProjectCreate,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.proj_leader))],
) -> dict[str, object]:
    sub_project = await service.create_sub_project(actor=current_user, payload=payload)
    return success_response(serialize_sub_project(sub_project))


@router.get("/{sub_project_id}")
async def get_sub_project(
    sub_project_id: UUID,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    sub_project = await service.get_sub_project(actor=current_user, sub_project_id=sub_project_id)
    return success_response(serialize_sub_project(sub_project))


@router.put("/{sub_project_id}")
async def update_sub_project(
    sub_project_id: UUID,
    payload: SubProjectUpdate,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    sub_project = await service.update_sub_project(
        actor=current_user,
        sub_project_id=sub_project_id,
        payload=payload,
    )
    return success_response(serialize_sub_project(sub_project))
