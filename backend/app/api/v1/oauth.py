from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.users import User
from app.schemas.auth import TokenPairRead
from app.schemas.oauth import (
    OAuthAuthorizationStartRead,
    OAuthBindingRead,
    OAuthCallbackRequest,
    OAuthProviderRead,
)
from app.services.auth import create_auth_tokens
from app.services.oauth import (
    OAuthProviderConfig,
    OAuthService,
    RedisOAuthStateStore,
    SqlAlchemyOAuthBindingRepository,
    UrllibOAuthHttpClient,
)

router = APIRouter(prefix="/oauth", tags=["oauth"])


def build_oauth_provider_configs(settings: Settings) -> dict[str, OAuthProviderConfig]:
    if not settings.oauth_generic_enabled:
        return {}
    required_values = (
        settings.oauth_generic_client_id,
        settings.oauth_generic_client_secret,
        settings.oauth_generic_authorize_url,
        settings.oauth_generic_token_url,
        settings.oauth_generic_userinfo_url,
        settings.oauth_generic_redirect_uri,
    )
    if any(not value for value in required_values):
        return {}
    provider = OAuthProviderConfig(
        provider="generic_oidc",
        client_id=settings.oauth_generic_client_id,
        client_secret=settings.oauth_generic_client_secret,
        authorize_url=settings.oauth_generic_authorize_url,
        token_url=settings.oauth_generic_token_url,
        userinfo_url=settings.oauth_generic_userinfo_url,
        redirect_uri=settings.oauth_generic_redirect_uri,
        scope=settings.oauth_generic_scope,
        label=settings.oauth_generic_label,
        bind_redirect_uri=settings.oauth_generic_bind_redirect_uri or None,
    )
    return {provider.provider: provider}


def get_oauth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OAuthService:
    return OAuthService(
        providers=build_oauth_provider_configs(settings),
        state_store=RedisOAuthStateStore(settings.redis_url),
        http_client=UrllibOAuthHttpClient(),
        binding_repository=SqlAlchemyOAuthBindingRepository(session),
    )


def set_refresh_token_cookie(
    response: Response,
    *,
    refresh_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
    )


def serialize_tokens(user: User, response: Response, settings: Settings) -> dict[str, object]:
    tokens = create_auth_tokens(user, settings)
    set_refresh_token_cookie(response, refresh_token=tokens.refresh_token, settings=settings)
    return TokenPairRead(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    ).model_dump()


@router.get("/providers")
async def list_providers(
    service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> dict[str, object]:
    return success_response(
        [
            OAuthProviderRead(provider=config.provider, label=config.label).model_dump()
            for config in service.list_providers()
        ],
    )


@router.get("/bindings")
async def list_bindings(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> dict[str, object]:
    bindings = await service.list_user_bindings(current_user.id)
    return success_response(
        [OAuthBindingRead.model_validate(binding).model_dump(mode="json") for binding in bindings],
    )


@router.get("/{provider}/login")
async def start_login(
    provider: str,
    service: Annotated[OAuthService, Depends(get_oauth_service)],
    purpose: Annotated[Literal["login", "bind"], Query()] = "login",
) -> dict[str, object]:
    started = await service.start_login(provider, purpose=purpose)
    return success_response(OAuthAuthorizationStartRead(**started.__dict__).model_dump())


@router.get("/{provider}/callback")
async def complete_callback(
    provider: str,
    response: Response,
    service: Annotated[OAuthService, Depends(get_oauth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> dict[str, object]:
    identity = await service.handle_callback(provider=provider, code=code, state=state)
    user = await service.resolve_login_user(identity)
    return success_response(serialize_tokens(user, response, settings))


@router.post("/{provider}/bind")
async def bind_provider(
    provider: str,
    payload: OAuthCallbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> dict[str, object]:
    identity = await service.handle_callback(
        provider=provider,
        code=payload.code,
        state=payload.state,
    )
    binding = await service.bind_identity(user=current_user, identity=identity)
    return success_response(OAuthBindingRead.model_validate(binding).model_dump(mode="json"))


@router.delete("/{provider}/bind")
async def unbind_provider(
    provider: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> dict[str, object]:
    deleted = await service.delete_user_binding(user_id=current_user.id, provider=provider)
    return success_response({"unbound": deleted})
