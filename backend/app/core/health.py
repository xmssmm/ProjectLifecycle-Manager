from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine


async def check_database() -> str:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return "error"
    return "ok"


async def check_redis() -> str:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await cast(Awaitable[bool], redis_client.ping())
    except Exception:
        return "error"
    finally:
        await redis_client.aclose()
    return "ok"


async def collect_health() -> dict[str, str]:
    return {
        "database": await check_database(),
        "redis": await check_redis(),
    }
