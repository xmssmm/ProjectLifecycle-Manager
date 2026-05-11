from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.exceptions import AuthenticationError
from app.core.redis import create_redis_client
from app.models.users import User
from app.services.audit import set_audit_actor
from app.services.auth import (
    AuthTokenStore,
    RedisAuthTokenStore,
    get_active_user_by_id,
    validate_token_claims,
)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUserContext:
    user: User
    claims: dict[str, Any]
    token: str


def get_auth_token_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthTokenStore:
    return RedisAuthTokenStore(redis_client=create_redis_client(settings))


async def get_current_token_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    token_store: Annotated[AuthTokenStore, Depends(get_auth_token_store)],
) -> CurrentUserContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Missing bearer token")

    claims = await validate_token_claims(
        credentials.credentials,
        expected_type="access",
        token_store=token_store,
        settings=settings,
    )
    try:
        user_id = UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token subject") from exc

    user = await get_active_user_by_id(session, user_id)
    set_audit_actor(user.id)
    return CurrentUserContext(user=user, claims=claims, token=credentials.credentials)


async def get_current_user(
    context: Annotated[CurrentUserContext, Depends(get_current_token_context)],
) -> User:
    return context.user
