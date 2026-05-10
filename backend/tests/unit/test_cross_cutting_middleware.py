from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.middleware import (
    InMemoryRateLimitStore,
    MaxBodySizeMiddleware,
    RateLimitMiddleware,
)
from app.main import create_app


async def healthy_components() -> dict[str, str]:
    return {"database": "ok", "redis": "ok"}


def test_cors_uses_configured_origins() -> None:
    settings = Settings(cors_allow_origins="http://allowed.example")
    client = TestClient(create_app(settings=settings, health_checker=healthy_components))

    response = client.options(
        "/health",
        headers={
            "Origin": "http://allowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://allowed.example"


def test_default_cors_allows_localhost_and_loopback_dev_hosts() -> None:
    settings = Settings(cors_allow_origins=str(Settings.model_fields["cors_allow_origins"].default))

    assert "http://localhost:5173" in settings.cors_origins
    assert "http://127.0.0.1:5173" in settings.cors_origins


def test_security_headers_are_added_to_responses() -> None:
    client = TestClient(create_app(health_checker=healthy_components))

    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_rate_limit_returns_429_after_limit_is_exceeded() -> None:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=1,
        store=InMemoryRateLimitStore(),
    )

    @app.get("/limited")
    async def limited() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)

    assert client.get("/limited").status_code == 200
    response = client.get("/limited")

    assert response.status_code == 429
    assert response.json() == {
        "code": 1004,
        "message": "请求过于频繁",
        "data": {"limit_per_minute": 1},
    }


def test_request_size_limit_returns_413() -> None:
    app = FastAPI()
    app.add_middleware(MaxBodySizeMiddleware, max_body_size_bytes=4)

    @app.post("/upload")
    async def upload() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).post("/upload", content=b"too-large")

    assert response.status_code == 413
    assert response.json() == {
        "code": 2005,
        "message": "请求体过大",
        "data": {"max_body_size": 4},
    }


def test_openapi_metadata_is_customized() -> None:
    client = TestClient(create_app(health_checker=healthy_components))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "企业项目过程管理与资料归档系统 API"
    assert response.json()["info"]["version"] == "0.1.0"
    assert response.json()["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }


def test_health_returns_database_and_redis_status() -> None:
    client = TestClient(create_app(health_checker=healthy_components))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "status": "ok",
        "service": "backend",
        "database": "ok",
        "redis": "ok",
    }
