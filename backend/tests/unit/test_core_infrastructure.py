from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.contextvars import get_contextvars

from app.core.config import Settings
from app.core.exceptions import BusinessException, ResourceNotFoundError
from app.core.middleware import RequestIdMiddleware
from app.core.responses import success_response
from app.core.security import generate_jti, hash_password, verify_password
from app.main import create_app


def test_business_exception_maps_to_standard_error_response() -> None:
    app = create_app()

    @app.get("/raise-business-error")
    async def raise_business_error() -> None:
        raise BusinessException(
            code=3003,
            message="状态不允许",
            status_code=409,
            data={"status": "completed"},
        )

    response = TestClient(app).get("/raise-business-error")

    assert response.status_code == 409
    assert response.json() == {
        "code": 3003,
        "message": "状态不允许",
        "data": {"status": "completed"},
    }


def test_resource_not_found_maps_to_404_response() -> None:
    app = create_app()

    @app.get("/missing-resource")
    async def missing_resource() -> None:
        raise ResourceNotFoundError("项目不存在", data={"resource": "main_project"})

    response = TestClient(app).get("/missing-resource")

    assert response.status_code == 404
    assert response.json() == {
        "code": 4001,
        "message": "项目不存在",
        "data": {"resource": "main_project"},
    }


def test_request_id_middleware_adds_header_and_binds_log_context() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/request-id")
    async def request_id() -> dict[str, object]:
        return success_response({"request_id": get_contextvars().get("request_id")})

    response = TestClient(app).get("/request-id", headers={"X-Request-ID": "req-test"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-test"
    assert response.json()["data"]["request_id"] == "req-test"


def test_security_helpers_hash_password_and_generate_unique_jti() -> None:
    password_hash = hash_password("Stronger123!")

    assert password_hash != "Stronger123!"
    assert verify_password("Stronger123!", password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert generate_jti() != generate_jti()


def test_settings_read_environment_values(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_NAME", "Custom App")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")

    settings = Settings()

    assert settings.app_name == "Custom App"
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"
    assert settings.redis_url == "redis://localhost:6379/1"
