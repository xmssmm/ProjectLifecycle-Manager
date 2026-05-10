from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
from asyncio import to_thread
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ResourceConflictError
from app.models.oauth import OAuthBinding
from app.models.users import User, UserStatus

OAUTH_STATE_TTL_SECONDS = 10 * 60
OAUTH_LOGIN_ALLOWED_STATUSES = frozenset(
    {UserStatus.active, UserStatus.password_reset_required},
)


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
    label: str = "企业账号"
    bind_redirect_uri: str | None = None


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

    async def get_by_user_provider(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> OAuthBinding | None:
        ...

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        ...

    async def get_user_by_email(self, email: str) -> User | None:
        ...

    async def list_by_user(self, user_id: UUID) -> Sequence[OAuthBinding]:
        ...

    async def upsert_binding(
        self,
        *,
        user_id: UUID,
        identity: OAuthExternalIdentity,
    ) -> OAuthBinding:
        ...

    async def delete_by_user_provider(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> bool:
        ...

    async def commit(self) -> None:
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

    async def get_by_user_provider(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> OAuthBinding | None:
        result = await self._session.scalars(
            select(OAuthBinding).where(
                OAuthBinding.user_id == user_id,
                OAuthBinding.provider == provider,
            ),
        )
        return result.first()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        user = await self._session.get(User, user_id)
        return user if isinstance(user, User) else None

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self._session.scalars(
            select(User).where(User.email == email),
        )
        return result.first()

    async def list_by_user(self, user_id: UUID) -> Sequence[OAuthBinding]:
        result = await self._session.scalars(
            select(OAuthBinding)
            .where(OAuthBinding.user_id == user_id)
            .order_by(OAuthBinding.provider),
        )
        return list(result.all())

    async def upsert_binding(
        self,
        *,
        user_id: UUID,
        identity: OAuthExternalIdentity,
    ) -> OAuthBinding:
        binding = await self.get_by_provider_external_id(
            provider=identity.provider,
            external_id=identity.external_id,
        )
        if binding is not None and binding.user_id != user_id:
            raise ResourceConflictError("OAuth account is already bound to another user")

        if binding is None:
            binding = await self.get_by_user_provider(
                user_id=user_id,
                provider=identity.provider,
            )

        if binding is None:
            binding = OAuthBinding(
                user_id=user_id,
                provider=identity.provider,
                external_id=identity.external_id,
                email=identity.email,
                access_token_ciphertext=identity.access_token_ciphertext,
                refresh_token_ciphertext=identity.refresh_token_ciphertext,
                expires_at=identity.expires_at,
            )
            self._session.add(binding)
        else:
            binding.external_id = identity.external_id
            binding.email = identity.email
            binding.access_token_ciphertext = identity.access_token_ciphertext
            binding.refresh_token_ciphertext = identity.refresh_token_ciphertext
            binding.expires_at = identity.expires_at

        await self._session.flush()
        return binding

    async def delete_by_user_provider(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> bool:
        binding = await self.get_by_user_provider(user_id=user_id, provider=provider)
        if binding is None:
            return False
        await self._session.delete(binding)
        await self._session.flush()
        return True

    async def commit(self) -> None:
        await self._session.commit()


class InMemoryOAuthBindingRepository:
    def __init__(
        self,
        bindings: Sequence[OAuthBinding] | None = None,
        *,
        users: Sequence[User] | None = None,
    ) -> None:
        self.bindings = list(bindings or [])
        self.users = list(users or [])

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

    async def get_by_user_provider(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> OAuthBinding | None:
        return next(
            (
                binding
                for binding in self.bindings
                if binding.user_id == user_id and binding.provider == provider
            ),
            None,
        )

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    async def get_user_by_email(self, email: str) -> User | None:
        normalized = email.lower()
        return next(
            (
                user
                for user in self.users
                if user.email is not None and user.email.lower() == normalized
            ),
            None,
        )

    async def list_by_user(self, user_id: UUID) -> Sequence[OAuthBinding]:
        return [binding for binding in self.bindings if binding.user_id == user_id]

    async def upsert_binding(
        self,
        *,
        user_id: UUID,
        identity: OAuthExternalIdentity,
    ) -> OAuthBinding:
        binding = await self.get_by_provider_external_id(
            provider=identity.provider,
            external_id=identity.external_id,
        )
        if binding is not None and binding.user_id != user_id:
            raise ResourceConflictError("OAuth account is already bound to another user")

        if binding is None:
            binding = await self.get_by_user_provider(
                user_id=user_id,
                provider=identity.provider,
            )

        now = datetime.now(UTC)
        if binding is None:
            binding = OAuthBinding(
                id=uuid4(),
                user_id=user_id,
                provider=identity.provider,
                external_id=identity.external_id,
                email=identity.email,
                access_token_ciphertext=identity.access_token_ciphertext,
                refresh_token_ciphertext=identity.refresh_token_ciphertext,
                expires_at=identity.expires_at,
                created_at=now,
                updated_at=now,
            )
            self.bindings.append(binding)
        else:
            binding.external_id = identity.external_id
            binding.email = identity.email
            binding.access_token_ciphertext = identity.access_token_ciphertext
            binding.refresh_token_ciphertext = identity.refresh_token_ciphertext
            binding.expires_at = identity.expires_at
            binding.updated_at = now

        return binding

    async def delete_by_user_provider(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> bool:
        binding = await self.get_by_user_provider(user_id=user_id, provider=provider)
        if binding is None:
            return False
        self.bindings.remove(binding)
        return True

    async def commit(self) -> None:
        return None


class UrllibOAuthHttpClient:
    def __init__(self, *, timeout_seconds: float = 10.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def post_form(
        self,
        url: str,
        *,
        data: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        return await to_thread(self._post_form_sync, url, data=data, headers=headers)

    async def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        return await to_thread(self._get_json_sync, url, headers=headers)

    def _post_form_sync(
        self,
        url: str,
        *,
        data: Mapping[str, object],
        headers: Mapping[str, str] | None,
    ) -> Mapping[str, object]:
        body = urlencode({key: str(value) for key, value in data.items()}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                **dict(headers or {}),
            },
            method="POST",
        )
        return self._open_json(request)

    def _get_json_sync(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None,
    ) -> Mapping[str, object]:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", **dict(headers or {})},
            method="GET",
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> Mapping[str, object]:
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise AuthenticationError("OAuth provider request failed") from exc
        if not isinstance(payload, dict):
            raise AuthenticationError("OAuth provider response is invalid")
        return payload


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

    def list_providers(self) -> Sequence[OAuthProviderConfig]:
        return list(self._providers.values())

    async def start_login(
        self,
        provider: str,
        *,
        purpose: str = "login",
    ) -> OAuthAuthorizationStart:
        config = self._provider_config(provider)
        redirect_uri = (
            config.bind_redirect_uri
            if purpose == "bind" and config.bind_redirect_uri is not None
            else config.redirect_uri
        )
        state = secrets.token_urlsafe(32)
        await self._state_store.store_state(
            state,
            OAuthStatePayload(provider=provider, redirect_uri=redirect_uri),
            ttl_seconds=OAUTH_STATE_TTL_SECONDS,
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": config.client_id,
                "redirect_uri": redirect_uri,
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

    async def resolve_login_user(self, identity: OAuthExternalIdentity) -> User:
        user = await self._resolve_existing_or_verified_email_user(identity)
        await self._binding_repository.upsert_binding(user_id=user.id, identity=identity)
        user.last_login_at = self._now_provider()
        await self._binding_repository.commit()
        return user

    async def list_user_bindings(self, user_id: UUID) -> Sequence[OAuthBinding]:
        return await self._binding_repository.list_by_user(user_id)

    async def bind_identity(
        self,
        *,
        user: User,
        identity: OAuthExternalIdentity,
    ) -> OAuthBinding:
        if identity.bound_user_id is not None and identity.bound_user_id != user.id:
            raise ResourceConflictError("OAuth account is already bound to another user")
        if user.status not in OAUTH_LOGIN_ALLOWED_STATUSES:
            raise AuthenticationError("Invalid user")
        binding = await self._binding_repository.upsert_binding(
            user_id=user.id,
            identity=identity,
        )
        await self._binding_repository.commit()
        return binding

    async def delete_user_binding(
        self,
        *,
        user_id: UUID,
        provider: str,
    ) -> bool:
        deleted = await self._binding_repository.delete_by_user_provider(
            user_id=user_id,
            provider=provider,
        )
        await self._binding_repository.commit()
        return deleted

    def _provider_config(self, provider: str) -> OAuthProviderConfig:
        config = self._providers.get(provider)
        if config is None:
            raise AuthenticationError("Unknown OAuth provider")
        return config

    async def _resolve_existing_or_verified_email_user(
        self,
        identity: OAuthExternalIdentity,
    ) -> User:
        if identity.bound_user_id is not None:
            user = await self._binding_repository.get_user_by_id(identity.bound_user_id)
            if user is None:
                raise AuthenticationError("OAuth bound user is unavailable")
            if user.status not in OAUTH_LOGIN_ALLOWED_STATUSES:
                raise AuthenticationError("Invalid user")
            return user

        if not identity.email_verified or identity.email is None:
            raise AuthenticationError("OAuth account is not linked to a local user")

        user = await self._binding_repository.get_user_by_email(identity.email)
        if user is None or user.status not in OAUTH_LOGIN_ALLOWED_STATUSES:
            raise AuthenticationError("OAuth account is not linked to a local user")
        return user

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
