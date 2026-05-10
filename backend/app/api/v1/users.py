from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import AsyncSessionLocal, get_db_session
from app.core.deps import get_auth_token_store, get_current_user
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.schemas.sub_projects import (
    SubProjectBatchHandoverItem,
    SubProjectHandoverListRead,
    SubProjectHandoverRead,
    SubProjectListRead,
    SubProjectRead,
)
from app.schemas.users import (
    PasswordChangeRequest,
    PasswordResetRequest,
    UserCreate,
    UserListRead,
    UserRead,
    UserUpdate,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.auth import AuthTokenStore
from app.services.notifications import NotificationService, SqlAlchemyNotificationRepository
from app.services.sub_projects import SqlAlchemySubProjectRepository, SubProjectService
from app.services.users import (
    SqlAlchemyProjectAssignmentReader,
    SqlAlchemyUserRepository,
    UserService,
)

router = APIRouter(prefix="/users", tags=["users"])


def get_token_revoke_ttl_seconds(settings: Settings) -> int:
    return settings.jwt_refresh_token_expire_days * 24 * 60 * 60


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    token_store: Annotated[AuthTokenStore, Depends(get_auth_token_store)],
) -> UserService:
    return UserService(
        repository=SqlAlchemyUserRepository(session),
        token_store=token_store,
        project_reader=SqlAlchemyProjectAssignmentReader(session),
        token_revoke_ttl_seconds=get_token_revoke_ttl_seconds(settings),
    )


async def get_project_handover_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubProjectService:
    return SubProjectService(
        repository=SqlAlchemySubProjectRepository(session),
        notification_service=NotificationService(
            repository=SqlAlchemyNotificationRepository(session),
        ),
    )


def serialize_user(user: User) -> dict[str, object]:
    return UserRead.model_validate(user).model_dump(mode="json")


@router.get("")
async def list_users(
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
    role: Annotated[UserRole | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    users, total = await service.list_users(
        actor=current_user,
        role=role,
        page=page,
        page_size=page_size,
    )
    payload = UserListRead(
        items=[UserRead.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def create_user(
    payload: UserCreate,
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    user = await service.create_user(actor=current_user, payload=payload)
    return success_response(serialize_user(user))


@router.post("/me/change-password")
async def change_own_password(
    payload: PasswordChangeRequest,
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    user = await service.change_own_password(actor=current_user, payload=payload)
    return success_response(serialize_user(user))


@router.get("/handovers")
async def list_sub_project_handovers(
    service: Annotated[SubProjectService, Depends(get_project_handover_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
    sub_project_id: Annotated[UUID | None, Query()] = None,
    from_user_id: Annotated[UUID | None, Query()] = None,
    to_user_id: Annotated[UUID | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    handovers, total = await service.list_sub_project_handovers(
        actor=current_user,
        page=page,
        page_size=page_size,
        sub_project_id=sub_project_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
    )
    payload = SubProjectHandoverListRead(
        items=[SubProjectHandoverRead.model_validate(handover) for handover in handovers],
        total=total,
        page=page,
        page_size=page_size,
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/{user_id}/active-sub-projects")
async def list_active_sub_projects_for_leader(
    user_id: UUID,
    service: Annotated[SubProjectService, Depends(get_project_handover_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    sub_projects = await service.list_active_sub_projects_for_leader(
        actor=current_user,
        user_id=user_id,
    )
    payload = SubProjectListRead(
        items=[SubProjectRead.model_validate(sub_project) for sub_project in sub_projects],
        total=len(sub_projects),
        page=1,
        page_size=len(sub_projects),
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("/{user_id}/batch-handover")
async def batch_handover_sub_projects(
    user_id: UUID,
    payload: Annotated[list[SubProjectBatchHandoverItem], Body(min_length=1)],
    background_tasks: BackgroundTasks,
    service: Annotated[SubProjectService, Depends(get_project_handover_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    sub_projects = await service.batch_handover_sub_projects(
        actor=current_user,
        from_user_id=user_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(
        {
            "items": [
                SubProjectRead.model_validate(sub_project).model_dump(mode="json")
                for sub_project in sub_projects
            ],
            "total": len(sub_projects),
        },
    )


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    user = await service.get_user(actor=current_user, user_id=user_id)
    return success_response(serialize_user(user))


@router.put("/{user_id}")
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    background_tasks: BackgroundTasks,
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    user = await service.update_user(
        actor=current_user,
        user_id=user_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_user(user))


@router.delete("/{user_id}")
async def disable_user(
    user_id: UUID,
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    user = await service.disable_user(actor=current_user, user_id=user_id)
    return success_response(serialize_user(user))


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: UUID,
    payload: PasswordResetRequest,
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    user = await service.reset_password(actor=current_user, user_id=user_id, payload=payload)
    return success_response(serialize_user(user))
