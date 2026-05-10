from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.deps import get_auth_token_store, get_current_user
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.schemas.users import (
    PasswordChangeRequest,
    PasswordResetRequest,
    UserCreate,
    UserListRead,
    UserRead,
    UserUpdate,
)
from app.services.auth import AuthTokenStore
from app.services.users import NoopProjectAssignmentReader, SqlAlchemyUserRepository, UserService

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
        project_reader=NoopProjectAssignmentReader(),
        token_revoke_ttl_seconds=get_token_revoke_ttl_seconds(settings),
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
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    user = await service.update_user(actor=current_user, user_id=user_id, payload=payload)
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
