from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.models.oauth import OAuthBinding

OAUTH_STATE_TTL_SECONDS = 10 * 60


@dataclass(frozen=True)
class OAuthProviderConfig:
    provider: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    redirect_uri: str
    scope: str


@dataclass(frozen=True)
class OAuthStatePayload:
    provider: str
    redirect_uri: str


@dataclass(frozen=True)
class OAuthAuthorizationStart:
    authorization_url: str
    state: str


@dataclass(frozen=True)
class OAuthExternalIdentity:
    provider: str
    external_id: str
    email: str | None
    email_verified: bool
    display_name: str | None
    bound_user_id: UUID | None
    access_token_ciphertext: str
    refresh_token_ciphertext: str | None
    expires_at: datetime | None


class OAuthStateStore(Protocol):
    async def store_state(
        self,
        state: str,
        payload: OAuthStatePayload,
        *,
        ttl_seconds: int,
    ) -> None:
        ...

    async def pop_state(self, state: str) -> OAuthStatePayload | None:
        ...


class OAuthHttpClient(Protocol):
    async def post_form(
        self,
        url: str,
        *,
        data: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        ...

    async def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        ...


class OAuthBindingRepository(Protocol):
    async def get_by_provider_external_id(
        self,
        *,
        provider: str,
        external_id: str,
    ) -> OAuthBinding | None:
        ...


@dataclass
class InMemoryOAuthStateStore:
    values: dict[str, tuple[OAuthStatePayload, float]] | None = None

    async def store_state(
        self,
        state: str,
        payload: OAuthStatePayload,
        *,
        ttl_seconds: int,
    ) -> None:
        if self.values is None:
            self.values = {}
        self.values[state] = (payload, monotonic() + ttl_seconds)

    async def pop_state(self, state: str) -> OAuthStatePayload | None:
        payload = await self.peek_state(state)
        if self.values is not None:
            self.values.pop(state, None)
        return payload

    async def peek_state(self, state: str) -> OAuthStatePayload | None:
        if self.values is None:
            return None
        stored = self.values.get(state)
        if stored is None:
            return None
        payload, expires_at = stored
        if expires_at <= monotonic():
            self.values.pop(state, None)
            return None
        return payload


class RedisOAuthStateStore:
    def __init__(self, redis_url: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)

    async def store_state(
        self,
        state: str,
        payload: OAuthStatePayload,
        *,
        ttl_seconds: int,
    ) -> None:
        await self._client.setex(
            self._key(state),
            ttl_seconds,
            json.dumps(asdict(payload), separators=(",", ":")),
        )

    async def pop_state(self, state: str) -> OAuthStatePayload | None:
        key = self._key(state)
        value = await self._client.get(key)
        if value is None:
            return None
        await self._client.delete(key)
        payload = json.loads(value)
        if not isinstance(payload, dict):
            return None
        provider = payload.get("provider")
        redirect_uri = payload.get("redirect_uri")
        if not isinstance(provider, str) or not isinstance(redirect_uri, str):
            return None
        return OAuthStatePayload(provider=provider, redirect_uri=redirect_uri)

    @staticmethod
    def _key(state: str) -> str:
        return f"oauth:state:{state}"


class SqlAlchemyOAuthBindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_provider_external_id(
        self,
        *,
        provider: str,
        external_id: str,
    ) -> OAuthBinding | None:
        result = await self._session.scalars(
            select(OAuthBinding).where(
                OAuthBinding.provider == provider,
                OAuthBinding.external_id == external_id,
            ),
        )
        return result.first()


class InMemoryOAuthBindingRepository:
    def __init__(self, bindings: Sequence[OAuthBinding] | None = None) -> None:
        self.bindings = list(bindings or [])

    async def get_by_provider_external_id(
        self,
        *,
        provider: str,
        external_id: str,
    ) -> OAuthBinding | None:
        return next(
            (
                binding
                for binding in self.bindings
                if binding.provider == provider and binding.external_id == external_id
            ),
            None,
        )


class OAuthService:
    def __init__(
        self,
        *,
        providers: Mapping[str, OAuthProviderConfig],
        state_store: OAuthStateStore,
        http_client: OAuthHttpClient,
        binding_repository: OAuthBindingRepository,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._providers = dict(providers)
        self._state_store = state_store
        self._http_client = http_client
        self._binding_repository = binding_repository
        self._now_provider = now_provider

    async def start_login(self, provider: str) -> OAuthAuthorizationStart:
        config = self._provider_config(provider)
        state = secrets.token_urlsafe(32)
        await self._state_store.store_state(
            state,
            OAuthStatePayload(provider=provider, redirect_uri=config.redirect_uri),
            ttl_seconds=OAUTH_STATE_TTL_SECONDS,
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "scope": config.scope,
                "state": state,
            },
        )
        return OAuthAuthorizationStart(
            authorization_url=f"{config.authorize_url}?{query}",
            state=state,
        )

    async def handle_callback(
        self,
        *,
        provider: str,
        code: str,
        state: str,
    ) -> OAuthExternalIdentity:
        config = self._provider_config(provider)
        state_payload = await self._state_store.pop_state(state)
        if state_payload is None or state_payload.provider != provider:
            raise AuthenticationError("Invalid OAuth state")

        token_response = await self._http_client.post_form(
            config.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": state_payload.redirect_uri,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
            },
        )
        access_token = self._required_string(
            token_response,
            "access_token",
            message="OAuth token response is invalid",
        )
        refresh_token = self._optional_string(token_response, "refresh_token")
        expires_at = self._expires_at(token_response.get("expires_in"))

        userinfo = await self._http_client.get_json(
            config.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        external_id = self._external_id_from_userinfo(userinfo)
        email = self._optional_string(userinfo, "email")
        display_name = (
            self._optional_string(userinfo, "name")
            or self._optional_string(userinfo, "display_name")
            or self._optional_string(userinfo, "username")
        )
        email_verified = bool(userinfo.get("email_verified", False))
        binding = await self._binding_repository.get_by_provider_external_id(
            provider=provider,
            external_id=external_id,
        )
        return OAuthExternalIdentity(
            provider=provider,
            external_id=external_id,
            email=email,
            email_verified=email_verified,
            display_name=display_name,
            bound_user_id=binding.user_id if binding is not None else None,
            access_token_ciphertext=access_token,
            refresh_token_ciphertext=refresh_token,
            expires_at=expires_at,
        )

    def _provider_config(self, provider: str) -> OAuthProviderConfig:
        config = self._providers.get(provider)
        if config is None:
            raise AuthenticationError("Unknown OAuth provider")
        return config

    def _expires_at(self, expires_in: object) -> datetime | None:
        if expires_in is None:
            return None
        if not isinstance(expires_in, int | float | str) or isinstance(expires_in, bool):
            raise AuthenticationError("OAuth token response is invalid")
        try:
            seconds = int(expires_in)
        except ValueError:
            raise AuthenticationError("OAuth token response is invalid") from None
        if seconds <= 0:
            return None
        return self._now_provider() + timedelta(seconds=seconds)

    @classmethod
    def _external_id_from_userinfo(cls, userinfo: Mapping[str, object]) -> str:
        for key in ("sub", "id", "external_id", "userid", "unionid"):
            value = userinfo.get(key)
            if isinstance(value, str) and value:
                return value
        raise AuthenticationError("OAuth userinfo response is invalid")

    @staticmethod
    def _required_string(
        payload: Mapping[str, object],
        key: str,
        *,
        message: str,
    ) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise AuthenticationError(message)
        return value

    @staticmethod
    def _optional_string(payload: Mapping[str, object], key: str) -> str | None:
        value = payload.get(key)
        return value if isinstance(value, str) and value else None
