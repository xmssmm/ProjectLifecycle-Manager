from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic, perf_counter
from typing import Protocol
from uuid import uuid4

import structlog
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.responses import error_response
from app.services.audit import AuditContext, bind_audit_context, reset_audit_context


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        clear_contextvars()
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        bind_contextvars(request_id=request_id, user_id=None)
        audit_token = bind_audit_context(
            AuditContext(
                actor_id=None,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                request_id=request_id,
            ),
        )

        started_at = perf_counter()
        logger = structlog.get_logger("app.request")
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
            raise
        else:
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
            return response
        finally:
            reset_audit_context(audit_token)
            clear_contextvars()


class RateLimitStore(Protocol):
    async def increment(self, key: str, ttl_seconds: int) -> int:
        pass


@dataclass
class InMemoryRateLimitStore:
    values: dict[str, tuple[int, float]] | None = None

    async def increment(self, key: str, ttl_seconds: int) -> int:
        if self.values is None:
            self.values = {}

        now = monotonic()
        current_count, expires_at = self.values.get(key, (0, now + ttl_seconds))
        if expires_at <= now:
            current_count = 0
            expires_at = now + ttl_seconds

        current_count += 1
        self.values[key] = (current_count, expires_at)
        return current_count


class RedisRateLimitStore:
    def __init__(self, redis_url: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)

    async def increment(self, key: str, ttl_seconds: int) -> int:
        value = await self._client.incr(key)
        if int(value) == 1:
            await self._client.expire(key, ttl_seconds)
        return int(value)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        limit_per_minute: int,
        store: RateLimitStore,
    ) -> None:
        super().__init__(app)
        self._limit_per_minute = limit_per_minute
        self._store = store

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_host = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_host}:{request.url.path}"

        try:
            request_count = await self._store.increment(key, ttl_seconds=60)
        except Exception:
            return await call_next(request)

        if request_count > self._limit_per_minute:
            return JSONResponse(
                status_code=429,
                content=error_response(
                    code=1004,
                    message="请求过于频繁",
                    data={"limit_per_minute": self._limit_per_minute},
                ),
            )

        return await call_next(request)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_size_bytes: int,
    ) -> None:
        super().__init__(app)
        self._max_body_size_bytes = max_body_size_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_body_size_bytes:
            return JSONResponse(
                status_code=413,
                content=error_response(
                    code=2005,
                    message="请求体过大",
                    data={"max_body_size": self._max_body_size_bytes},
                ),
            )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response
