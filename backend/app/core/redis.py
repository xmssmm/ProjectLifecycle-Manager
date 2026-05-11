from __future__ import annotations

from typing import cast

from redis.asyncio import Redis
from redis.asyncio.sentinel import Sentinel

from app.core.config import Settings, get_settings


def create_redis_client(settings: Settings | None = None) -> Redis:
    resolved_settings = settings or get_settings()
    if not resolved_settings.redis_sentinel_enabled:
        return Redis.from_url(resolved_settings.redis_url, decode_responses=True)

    sentinel_kwargs = {}
    if resolved_settings.redis_sentinel_password:
        sentinel_kwargs["password"] = resolved_settings.redis_sentinel_password

    sentinel = Sentinel(  # type: ignore[no-untyped-call]
        resolved_settings.redis_sentinel_host_tuples,
        socket_timeout=resolved_settings.redis_sentinel_socket_timeout_seconds,
        sentinel_kwargs=sentinel_kwargs,
    )
    return cast(
        Redis,
        sentinel.master_for(
            resolved_settings.redis_sentinel_master_name,
            db=resolved_settings.redis_sentinel_db,
            password=resolved_settings.redis_sentinel_password or None,
            decode_responses=True,
            socket_timeout=resolved_settings.redis_sentinel_socket_timeout_seconds,
        ),
    )
