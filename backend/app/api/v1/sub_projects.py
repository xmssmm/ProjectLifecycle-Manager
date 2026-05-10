from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.sub_projects import SubProject
from app.models.users import User, UserRole
from app.schemas.sub_projects import (
    SubProjectCreate,
    SubProjectHandoverRequest,
    SubProjectListRead,
    SubProjectMemberCreate,
    SubProjectMemberListRead,
    SubProjectMemberRead,
    SubProjectRead,
    SubProjectReviewRequest,
    SubProjectTerminateRequest,
    SubProjectUpdate,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.notification_runtime import build_notification_service
from app.services.sub_projects import SqlAlchemySubProjectRepository, SubProjectService

router = APIRouter(prefix="/sub-projects", tags=["sub-projects"])


async def get_sub_project_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubProjectService:
    return SubProjectService(
        repository=SqlAlchemySubProjectRepository(session),
        notification_service=build_notification_service(session=session),
    )


def serialize_sub_project(sub_project: SubProject) -> dict[str, object]:
    return SubProjectRead.model_validate(sub_project).model_dump(mode="json")


def serialize_sub_project_member(member: object) -> dict[str, object]:
    return SubProjectMemberRead.model_validate(member).model_dump(mode="json")


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


@router.get("/{sub_project_id}/members")
async def list_sub_project_members(
    sub_project_id: UUID,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    members = await service.list_sub_project_members(
        actor=current_user,
        sub_project_id=sub_project_id,
    )
    payload = SubProjectMemberListRead(
        items=[SubProjectMemberRead.model_validate(member) for member in members],
        total=len(members),
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("/{sub_project_id}/members")
async def add_sub_project_member(
    sub_project_id: UUID,
    payload: SubProjectMemberCreate,
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    member = await service.add_sub_project_member(
        actor=current_user,
        sub_project_id=sub_project_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_sub_project_member(member))


@router.delete("/{sub_project_id}/members/{user_id}")
async def remove_sub_project_member(
    sub_project_id: UUID,
    user_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    member = await service.remove_sub_project_member(
        actor=current_user,
        sub_project_id=sub_project_id,
        user_id=user_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_sub_project_member(member))


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


@router.post("/{sub_project_id}/submit")
async def submit_sub_project(
    sub_project_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    sub_project = await service.submit_sub_project(
        actor=current_user,
        sub_project_id=sub_project_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_sub_project(sub_project))


@router.post("/{sub_project_id}/review")
async def review_sub_project(
    sub_project_id: UUID,
    payload: SubProjectReviewRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    sub_project = await service.review_sub_project(
        actor=current_user,
        sub_project_id=sub_project_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_sub_project(sub_project))


@router.post("/{sub_project_id}/close")
async def close_sub_project(
    sub_project_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.dept_manager))],
) -> dict[str, object]:
    sub_project = await service.close_sub_project(
        actor=current_user,
        sub_project_id=sub_project_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_sub_project(sub_project))


@router.post("/{sub_project_id}/terminate")
async def terminate_sub_project(
    sub_project_id: UUID,
    payload: SubProjectTerminateRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    sub_project = await service.terminate_sub_project(
        actor=current_user,
        sub_project_id=sub_project_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_sub_project(sub_project))


@router.post("/{sub_project_id}/handover")
async def handover_sub_project(
    sub_project_id: UUID,
    payload: SubProjectHandoverRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_sub_project_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    sub_project = await service.handover_sub_project(
        actor=current_user,
        sub_project_id=sub_project_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_sub_project(sub_project))
