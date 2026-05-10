from fastapi.testclient import TestClient

from app.main import create_app


async def healthy_components() -> dict[str, str]:
    return {"database": "ok", "redis": "ok"}


def test_health_check_returns_standard_success_payload() -> None:
    client = TestClient(create_app(health_checker=healthy_components))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "success",
        "data": {
            "status": "ok",
            "service": "backend",
            "database": "ok",
            "redis": "ok",
        },
    }
