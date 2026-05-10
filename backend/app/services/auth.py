from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AccountLockedError, AuthenticationError
from app.core.security import create_jwt_token, verify_password
from app.models.users import User, UserStatus

AUTH_FAILURE_LIMIT = 5
AUTH_FAILURE_TTL_SECONDS = 30 * 60


class AuthFailureStore(Protocol):
    async def get_fail_count(self, key: str) -> int:
        ...

    async def increment_fail_count(self, key: str, ttl_seconds: int) -> int:
        ...

    async def reset_fail_count(self, key: str) -> None:
        ...


@dataclass
class InMemoryAuthFailureStore:
    values: dict[str, tuple[int, float]] | None = None

    async def get_fail_count(self, key: str) -> int:
        if self.values is None:
            return 0
        count, expires_at = self.values.get(key, (0, monotonic()))
        if expires_at <= monotonic():
            self.values.pop(key, None)
            return 0
        return count

    async def increment_fail_count(self, key: str, ttl_seconds: int) -> int:
        if self.values is None:
            self.values = {}
        current = await self.get_fail_count(key)
        count = current + 1
        self.values[key] = (count, monotonic() + ttl_seconds)
        return count

    async def reset_fail_count(self, key: str) -> None:
        if self.values is not None:
            self.values.pop(key, None)


class RedisAuthFailureStore:
    def __init__(self, redis_url: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)

    async def get_fail_count(self, key: str) -> int:
        value = await self._client.get(key)
        return int(value or 0)

    async def increment_fail_count(self, key: str, ttl_seconds: int) -> int:
        value = await self._client.incr(key)
        if int(value) == 1:
            await self._client.expire(key, ttl_seconds)
        return int(value)

    async def reset_fail_count(self, key: str) -> None:
        await self._client.delete(key)


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class JwtSigningConfig:
    key: str
    algorithm: str


def get_auth_failure_key(user_id: UUID) -> str:
    return f"auth:fail:{user_id}"


def get_jwt_signing_config(settings: Settings) -> JwtSigningConfig:
    algorithm = settings.jwt_algorithm
    if algorithm.upper().startswith("HS"):
        return JwtSigningConfig(key=settings.jwt_secret_key, algorithm=algorithm)

    private_key_path = Path(settings.jwt_private_key_path)
    if private_key_path.exists():
        return JwtSigningConfig(
            key=private_key_path.read_text(encoding="utf-8"),
            algorithm=algorithm,
        )

    if settings.app_env == "production":
        raise RuntimeError("JWT private key file is required in production")

    return JwtSigningConfig(key=settings.jwt_secret_key, algorithm="HS256")


def create_auth_tokens(user: User, settings: Settings) -> AuthTokens:
    signing = get_jwt_signing_config(settings)
    extra_claims = {
        "role": user.role.value,
        "username": user.username,
    }
    access_token = create_jwt_token(
        subject=str(user.id),
        key=signing.key,
        algorithm=signing.algorithm,
        token_type="access",
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
        extra_claims=extra_claims,
    )
    refresh_token = create_jwt_token(
        subject=str(user.id),
        key=signing.key,
        algorithm=signing.algorithm,
        token_type="refresh",
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
        extra_claims=extra_claims,
    )
    return AuthTokens(access_token=access_token, refresh_token=refresh_token)


async def authenticate_user(
    *,
    user: User | None,
    password: str,
    failure_store: AuthFailureStore,
    settings: Settings,
) -> AuthTokens:
    if user is None or user.status != UserStatus.active:
        raise AuthenticationError("Invalid username or password")

    failure_key = get_auth_failure_key(user.id)
    if await failure_store.get_fail_count(failure_key) >= AUTH_FAILURE_LIMIT:
        raise AccountLockedError(data={"ttl_seconds": AUTH_FAILURE_TTL_SECONDS})

    if not verify_password(password, user.password_hash):
        failures = await failure_store.increment_fail_count(
            failure_key,
            ttl_seconds=AUTH_FAILURE_TTL_SECONDS,
        )
        if failures >= AUTH_FAILURE_LIMIT:
            raise AccountLockedError(data={"ttl_seconds": AUTH_FAILURE_TTL_SECONDS})
        raise AuthenticationError("Invalid username or password")

    await failure_store.reset_fail_count(failure_key)
    user.last_login_at = datetime.now(UTC)
    return create_auth_tokens(user, settings)


async def login_user(
    *,
    session: AsyncSession,
    username: str,
    password: str,
    failure_store: AuthFailureStore,
    settings: Settings,
) -> AuthTokens:
    user = await session.scalar(select(User).where(User.username == username))
    tokens = await authenticate_user(
        user=user,
        password=password,
        failure_store=failure_store,
        settings=settings,
    )
    await session.commit()
    return tokens
