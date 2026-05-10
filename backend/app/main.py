from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.v1.auth import get_auth_failure_store
from app.api.v1.auth import router as auth_router
from app.core.config import Settings, get_settings
from app.core.exceptions import BusinessException, business_exception_handler
from app.core.health import collect_health
from app.core.middleware import (
    MaxBodySizeMiddleware,
    RateLimitMiddleware,
    RateLimitStore,
    RedisRateLimitStore,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
)
from app.core.responses import success_response
from app.services.auth import AuthFailureStore, RedisAuthFailureStore

HealthChecker = Callable[[], Awaitable[dict[str, str]]]


def install_openapi_customization(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        components = openapi_schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


def create_app(
    *,
    settings: Settings | None = None,
    rate_limit_store: RateLimitStore | None = None,
    auth_failure_store: AuthFailureStore | None = None,
    health_checker: HealthChecker | None = None,
) -> FastAPI:
    configure_logging()
    resolved_settings = settings or get_settings()
    resolved_health_checker = health_checker or collect_health
    resolved_rate_limit_store = rate_limit_store or RedisRateLimitStore(resolved_settings.redis_url)
    resolved_auth_failure_store = auth_failure_store or RedisAuthFailureStore(
        resolved_settings.redis_url,
    )

    app = FastAPI(
        title="企业项目过程管理与资料归档系统 API",
        version="0.1.0",
        description="企业项目过程管理与资料归档系统后端接口。",
        openapi_tags=[
            {"name": "auth", "description": "Authentication endpoints."},
            {"name": "system", "description": "系统健康、版本与基础能力。"},
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=resolved_settings.rate_limit_per_minute,
        store=resolved_rate_limit_store,
    )
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_body_size_bytes=resolved_settings.max_upload_size_bytes,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.dependency_overrides[get_auth_failure_store] = lambda: resolved_auth_failure_store
    app.include_router(auth_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        components = await resolved_health_checker()
        overall_status = (
            "ok" if all(status == "ok" for status in components.values()) else "degraded"
        )
        return success_response(
            {
                "status": overall_status,
                "service": "backend",
                **components,
            }
        )

    install_openapi_customization(app)
    return app


app = create_app()
