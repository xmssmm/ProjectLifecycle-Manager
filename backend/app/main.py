from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.external.v1.router import router as external_api_router
from app.api.v1.acceptance_steps import router as acceptance_steps_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.archives import router as archives_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.auth import get_auth_failure_store
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.departments import router as departments_router
from app.api.v1.documents import router as documents_router
from app.api.v1.handover_requests import router as handover_requests_router
from app.api.v1.main_projects import router as main_projects_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.oauth import router as oauth_router
from app.api.v1.payments import router as payments_router
from app.api.v1.phases import router as phases_router
from app.api.v1.reports import router as reports_router
from app.api.v1.revoke_requests import router as revoke_requests_router
from app.api.v1.search import router as search_router
from app.api.v1.sub_projects import router as sub_projects_router
from app.api.v1.system import router as system_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.users import router as users_router
from app.api.v1.webhooks import router as webhooks_router
from app.core.config import Settings, get_settings
from app.core.db import AsyncSessionLocal
from app.core.deps import get_auth_token_store
from app.core.exceptions import BusinessException, business_exception_handler
from app.core.health import collect_health
from app.core.metrics import (
    CONTENT_TYPE_LATEST,
    PrometheusMetricsMiddleware,
    create_http_metrics,
)
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
from app.services.auth import (
    AuthFailureStore,
    AuthTokenStore,
    RedisAuthFailureStore,
    RedisAuthTokenStore,
)
from app.services.system_health import (
    SqlAlchemyRoleHealthReader,
    SystemHealthService,
    SystemHealthWarning,
)

HealthChecker = Callable[[], Awaitable[dict[str, str]]]
HealthWarningChecker = Callable[[], Awaitable[list[SystemHealthWarning]]]
LifespanContext = Callable[[FastAPI], AbstractAsyncContextManager[None]]


async def collect_startup_health_warnings() -> list[SystemHealthWarning]:
    async with AsyncSessionLocal() as session:
        service = SystemHealthService(role_reader=SqlAlchemyRoleHealthReader(session))
        return await service.collect_warnings()


def build_startup_health_warning_lifespan(
    checker: HealthWarningChecker,
) -> LifespanContext:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger = structlog.get_logger("app.system_health")
        try:
            warnings = await checker()
        except Exception:
            logger.exception("system.health_warnings_check_failed")
        else:
            logger.info(
                "system.health_warnings_checked",
                warning_count=len(warnings),
                warnings=warnings,
            )
        yield

    return lifespan


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
    auth_token_store: AuthTokenStore | None = None,
    health_checker: HealthChecker | None = None,
    health_warning_checker: HealthWarningChecker | None = None,
) -> FastAPI:
    configure_logging()
    resolved_settings = settings or get_settings()
    resolved_health_checker = health_checker or collect_health
    resolved_rate_limit_store = rate_limit_store or RedisRateLimitStore(resolved_settings.redis_url)
    resolved_auth_failure_store = auth_failure_store or RedisAuthFailureStore(
        resolved_settings.redis_url,
    )
    resolved_auth_token_store = auth_token_store or RedisAuthTokenStore(resolved_settings.redis_url)
    http_metrics = create_http_metrics()
    lifespan_context = (
        build_startup_health_warning_lifespan(health_warning_checker)
        if health_warning_checker is not None
        else None
    )

    app = FastAPI(
        title="企业项目过程管理与资料归档系统 API",
        version="0.1.0",
        description="企业项目过程管理与资料归档系统后端接口。",
        lifespan=lifespan_context,
        openapi_tags=[
            {"name": "external-api", "description": "External read-only API endpoints."},
            {"name": "webhooks", "description": "Webhook endpoint and delivery endpoints."},
            {"name": "acceptance-steps", "description": "Acceptance step endpoints."},
            {"name": "api-keys", "description": "API key management endpoints."},
            {"name": "archives", "description": "Archive batch and restore endpoints."},
            {"name": "audit-logs", "description": "Audit log query endpoints."},
            {"name": "dashboard", "description": "Role-scoped dashboard endpoints."},
            {"name": "payments", "description": "Payment creation and reversal endpoints."},
            {"name": "reports", "description": "Report generation and progress endpoints."},
            {"name": "notifications", "description": "Notification query endpoints."},
            {"name": "oauth", "description": "OAuth2/OIDC SSO endpoints."},
            {"name": "revoke-requests", "description": "Phase revoke request endpoints."},
            {"name": "search", "description": "Document full-text search endpoints."},
            {"name": "handover-requests", "description": "Self-service handover workflow."},
            {"name": "auth", "description": "Authentication endpoints."},
            {"name": "users", "description": "用户管理接口。"},
            {"name": "departments", "description": "部门管理接口。"},
            {"name": "main-projects", "description": "主项目管理接口。"},
            {"name": "sub-projects", "description": "子项目管理接口。"},
            {"name": "phases", "description": "环节查询与流转接口。"},
            {"name": "documents", "description": "文档上传、版本与归档接口。"},
            {"name": "tasks", "description": "任务 CRUD、指派与完成接口。"},
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
    app.add_middleware(PrometheusMetricsMiddleware, metrics=http_metrics)
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.dependency_overrides[get_settings] = lambda: resolved_settings
    app.dependency_overrides[get_auth_failure_store] = lambda: resolved_auth_failure_store
    app.dependency_overrides[get_auth_token_store] = lambda: resolved_auth_token_store
    app.include_router(external_api_router)
    app.include_router(acceptance_steps_router, prefix="/api/v1")
    app.include_router(api_keys_router, prefix="/api/v1")
    app.include_router(archives_router, prefix="/api/v1")
    app.include_router(audit_logs_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(departments_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(handover_requests_router, prefix="/api/v1")
    app.include_router(main_projects_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(oauth_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(phases_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(revoke_requests_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(sub_projects_router, prefix="/api/v1")
    app.include_router(system_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/api/v1")

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

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=http_metrics.render(), media_type=CONTENT_TYPE_LATEST)

    install_openapi_customization(app)
    return app


app = create_app(health_warning_checker=collect_startup_health_warnings)
