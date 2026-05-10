from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any, Protocol
from uuid import UUID

from jose import JWTError  # type: ignore[import-untyped]
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AccountLockedError, AuthenticationError
from app.core.security import create_jwt_token, decode_jwt_token, verify_password
from app.models.users import User, UserStatus

AUTH_FAILURE_LIMIT = 5
AUTH_FAILURE_TTL_SECONDS = 30 * 60
LOGIN_ALLOWED_STATUSES = frozenset({UserStatus.active, UserStatus.password_reset_required})


class AuthFailureStore(Protocol):
    async def get_fail_count(self, key: str) -> int:
        ...

    async def increment_fail_count(self, key: str, ttl_seconds: int) -> int:
        ...

    async def reset_fail_count(self, key: str) -> None:
        ...


class AuthTokenStore(Protocol):
    async def blacklist_jti(self, jti: str, ttl_seconds: int) -> None:
        ...

    async def is_jti_blacklisted(self, jti: str) -> bool:
        ...

    async def revoke_user_tokens(self, user_id: str, ttl_seconds: int) -> None:
        ...

    async def get_user_revoked_after(self, user_id: str) -> int | None:
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


@dataclass
class InMemoryAuthTokenStore:
    blacklisted_jtis: dict[str, float] | None = None
    user_revoked_after: dict[str, tuple[int, float]] | None = None

    async def blacklist_jti(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        if self.blacklisted_jtis is None:
            self.blacklisted_jtis = {}
        self.blacklisted_jtis[jti] = monotonic() + ttl_seconds

    async def is_jti_blacklisted(self, jti: str) -> bool:
        if self.blacklisted_jtis is None:
            return False
        expires_at = self.blacklisted_jtis.get(jti)
        if expires_at is None:
            return False
        if expires_at <= monotonic():
            self.blacklisted_jtis.pop(jti, None)
            return False
        return True

    async def revoke_user_tokens(self, user_id: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        if self.user_revoked_after is None:
            self.user_revoked_after = {}
        self.user_revoked_after[user_id] = (
            int(datetime.now(UTC).timestamp()),
            monotonic() + ttl_seconds,
        )

    async def get_user_revoked_after(self, user_id: str) -> int | None:
        if self.user_revoked_after is None:
            return None
        revoked = self.user_revoked_after.get(user_id)
        if revoked is None:
            return None
        revoked_after, expires_at = revoked
        if expires_at <= monotonic():
            self.user_revoked_after.pop(user_id, None)
            return None
        return revoked_after


class RedisAuthTokenStore:
    def __init__(self, redis_url: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)

    async def blacklist_jti(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        await self._client.setex(f"auth:blacklist:{jti}", ttl_seconds, "1")

    async def is_jti_blacklisted(self, jti: str) -> bool:
        return bool(await self._client.exists(f"auth:blacklist:{jti}"))

    async def revoke_user_tokens(self, user_id: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        await self._client.setex(
            f"auth:user_revoked_after:{user_id}",
            ttl_seconds,
            str(int(datetime.now(UTC).timestamp())),
        )

    async def get_user_revoked_after(self, user_id: str) -> int | None:
        value = await self._client.get(f"auth:user_revoked_after:{user_id}")
        return int(value) if value is not None else None


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


def get_jwt_verification_config(settings: Settings) -> JwtSigningConfig:
    algorithm = settings.jwt_algorithm
    if algorithm.upper().startswith("HS"):
        return JwtSigningConfig(key=settings.jwt_secret_key, algorithm=algorithm)

    public_key_path = Path(settings.jwt_public_key_path)
    if public_key_path.exists():
        return JwtSigningConfig(
            key=public_key_path.read_text(encoding="utf-8"),
            algorithm=algorithm,
        )

    if settings.app_env == "production":
        raise RuntimeError("JWT public key file is required in production")

    return JwtSigningConfig(key=settings.jwt_secret_key, algorithm="HS256")


def create_access_token(user: User, settings: Settings) -> str:
    signing = get_jwt_signing_config(settings)
    extra_claims = {
        "role": user.role.value,
        "username": user.username,
    }
    return create_jwt_token(
        subject=str(user.id),
        key=signing.key,
        algorithm=signing.algorithm,
        token_type="access",
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
        extra_claims=extra_claims,
    )


def create_auth_tokens(user: User, settings: Settings) -> AuthTokens:
    signing = get_jwt_signing_config(settings)
    extra_claims = {
        "role": user.role.value,
        "username": user.username,
    }
    access_token = create_access_token(user, settings)
    refresh_token = create_jwt_token(
        subject=str(user.id),
        key=signing.key,
        algorithm=signing.algorithm,
        token_type="refresh",
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
        extra_claims=extra_claims,
    )
    return AuthTokens(access_token=access_token, refresh_token=refresh_token)


def get_token_ttl_seconds(claims: dict[str, Any]) -> int:
    expires_at = int(claims.get("exp", 0))
    now = int(datetime.now(UTC).timestamp())
    return max(expires_at - now, 0)


async def validate_token_claims(
    token: str,
    *,
    expected_type: str,
    token_store: AuthTokenStore,
    settings: Settings,
) -> dict[str, Any]:
    verification = get_jwt_verification_config(settings)
    try:
        claims = decode_jwt_token(
            token,
            key=verification.key,
            algorithms=[verification.algorithm],
        )
    except JWTError as exc:
        raise AuthenticationError("Invalid token") from exc

    if claims.get("type") != expected_type:
        raise AuthenticationError("Invalid token type")

    jti = claims.get("jti")
    subject = claims.get("sub")
    if not isinstance(jti, str) or not isinstance(subject, str):
        raise AuthenticationError("Invalid token claims")

    if await token_store.is_jti_blacklisted(jti):
        raise AuthenticationError("Token has been revoked")

    issued_at = int(claims.get("iat", 0))
    revoked_after = await token_store.get_user_revoked_after(subject)
    if revoked_after is not None and issued_at <= revoked_after:
        raise AuthenticationError("Token has been revoked")

    return claims


async def get_active_user_by_id(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if not isinstance(user, User) or user.status not in LOGIN_ALLOWED_STATUSES:
        raise AuthenticationError("Invalid user")
    return user


async def authenticate_user(
    *,
    user: User | None,
    password: str,
    failure_store: AuthFailureStore,
    settings: Settings,
) -> AuthTokens:
    if user is None or user.status not in LOGIN_ALLOWED_STATUSES:
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
