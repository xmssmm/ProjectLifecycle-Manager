from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.exceptions import AuthenticationError, BusinessException
from app.core.middleware import RateLimitStore, RedisRateLimitStore
from app.models.api_keys import ApiKey
from app.services.api_keys import ApiKeyService, SqlAlchemyApiKeyRepository

EXTERNAL_API_RATE_LIMIT_PER_HOUR = 1000
EXTERNAL_API_RATE_LIMIT_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class ExternalApiContext:
    api_key: ApiKey


class ExternalApiRateLimitExceededError(BusinessException):
    def __init__(self) -> None:
        super().__init__(
            code=1004,
            message="External API rate limit exceeded",
            status_code=429,
            data={"limit": EXTERNAL_API_RATE_LIMIT_PER_HOUR, "window_seconds": 3600},
        )


class ExternalApiRateLimitStore(Protocol):
    async def hit(
        self,
        *,
        api_key_id: UUID,
        limit: int = EXTERNAL_API_RATE_LIMIT_PER_HOUR,
        window: timedelta = EXTERNAL_API_RATE_LIMIT_WINDOW,
    ) -> None:
        ...


class InMemoryExternalApiRateLimitStore:
    def __init__(self, now_provider: Callable[[], datetime] | None = None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._hits: dict[UUID, tuple[datetime, int]] = {}

    async def hit(
        self,
        *,
        api_key_id: UUID,
        limit: int = EXTERNAL_API_RATE_LIMIT_PER_HOUR,
        window: timedelta = EXTERNAL_API_RATE_LIMIT_WINDOW,
    ) -> None:
        now = self._now_provider()
        window_start, count = self._hits.get(api_key_id, (now, 0))
        if now - window_start >= window:
            window_start = now
            count = 0
        if count >= limit:
            raise ExternalApiRateLimitExceededError()
        self._hits[api_key_id] = (window_start, count + 1)


class RedisExternalApiRateLimitStore:
    def __init__(
        self,
        counter_store: RateLimitStore,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._counter_store = counter_store
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def hit(
        self,
        *,
        api_key_id: UUID,
        limit: int = EXTERNAL_API_RATE_LIMIT_PER_HOUR,
        window: timedelta = EXTERNAL_API_RATE_LIMIT_WINDOW,
    ) -> None:
        hour_bucket = self._now_provider().strftime("%Y%m%d%H")
        key = f"external_api:{api_key_id}:{hour_bucket}"
        count = await self._counter_store.increment(key, ttl_seconds=int(window.total_seconds()))
        if count > limit:
            raise ExternalApiRateLimitExceededError()


@lru_cache
def build_external_rate_limit_store(redis_url: str) -> RedisExternalApiRateLimitStore:
    return RedisExternalApiRateLimitStore(counter_store=RedisRateLimitStore(redis_url))


async def get_external_api_key_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiKeyService:
    return ApiKeyService(repository=SqlAlchemyApiKeyRepository(session))


async def get_external_rate_limit_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExternalApiRateLimitStore:
    return build_external_rate_limit_store(settings.redis_url)


def require_external_permission(permission: str) -> Callable[..., Awaitable[ExternalApiContext]]:
    async def dependency(
        service: Annotated[ApiKeyService, Depends(get_external_api_key_service)],
        rate_store: Annotated[
            ExternalApiRateLimitStore,
            Depends(get_external_rate_limit_store),
        ],
        api_key_token: Annotated[str | None, Header(alias="X-API-Key")] = None,
    ) -> ExternalApiContext:
        if not api_key_token:
            raise AuthenticationError("Missing API key")
        api_key = await service.authenticate(
            token=api_key_token,
            required_permission=permission,
        )
        await rate_store.hit(api_key_id=api_key.id)
        return ExternalApiContext(api_key=api_key)

    return dependency
