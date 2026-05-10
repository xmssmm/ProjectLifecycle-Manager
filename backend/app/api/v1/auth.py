from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.responses import success_response
from app.schemas.auth import LoginRequest, TokenPairRead
from app.services.auth import AuthFailureStore, RedisAuthFailureStore, login_user

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_failure_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthFailureStore:
    return RedisAuthFailureStore(settings.redis_url)


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
