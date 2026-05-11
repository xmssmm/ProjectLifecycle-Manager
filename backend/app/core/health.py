from collections.abc import Awaitable
from typing import cast

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.core.redis import create_redis_client


async def check_database() -> str:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return "error"
    return "ok"


async def check_redis() -> str:
    settings = get_settings()
    redis_client = create_redis_client(settings)
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
