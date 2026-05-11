from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.deps import CurrentUserContext, get_auth_token_store, get_current_token_context
from app.core.exceptions import AuthenticationError
from app.core.redis import create_redis_client
from app.core.responses import success_response
from app.schemas.auth import AccessTokenRead, CurrentUserRead, LoginRequest, TokenPairRead
from app.services.auth import (
    AuthFailureStore,
    AuthTokenStore,
    RedisAuthFailureStore,
    create_access_token,
    get_active_user_by_id,
    get_token_ttl_seconds,
    login_user,
    validate_token_claims,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_failure_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthFailureStore:
    return RedisAuthFailureStore(redis_client=create_redis_client(settings))


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    failure_store: Annotated[AuthFailureStore, Depends(get_auth_failure_store)],
) -> dict[str, object]:
    tokens = await login_user(
        session=session,
        username=payload.username,
        password=payload.password,
        failure_store=failure_store,
        settings=settings,
    )
    max_age = settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    response.set_cookie(
        "refresh_token",
        tokens.refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
    )
    return success_response(
        TokenPairRead(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
        ).model_dump(),
    )


@router.post("/refresh")
async def refresh(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    token_store: Annotated[AuthTokenStore, Depends(get_auth_token_store)],
    refresh_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> dict[str, object]:
    if refresh_token is None:
        raise AuthenticationError("Missing refresh token")
    claims = await validate_token_claims(
        refresh_token,
        expected_type="refresh",
        token_store=token_store,
        settings=settings,
    )
    user = await get_active_user_by_id(session, UUID(str(claims["sub"])))
    access_token = create_access_token(user, settings)
    return success_response(AccessTokenRead(access_token=access_token).model_dump())


@router.post("/logout")
async def logout(
    response: Response,
    context: Annotated[CurrentUserContext, Depends(get_current_token_context)],
    token_store: Annotated[AuthTokenStore, Depends(get_auth_token_store)],
) -> dict[str, object]:
    jti = str(context.claims["jti"])
    await token_store.blacklist_jti(jti, get_token_ttl_seconds(context.claims))
    response.delete_cookie("refresh_token")
    return success_response({"logged_out": True})


@router.get("/me")
async def me(
    context: Annotated[CurrentUserContext, Depends(get_current_token_context)],
) -> dict[str, object]:
    user = context.user
    return success_response(
        CurrentUserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            dept_id=user.dept_id,
            status=user.status,
            timezone=user.timezone,
        ).model_dump(mode="json"),
    )
