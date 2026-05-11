from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.external.v1.deps import (
    InMemoryExternalApiRateLimitStore,
    RedisExternalApiRateLimitStore,
    get_external_api_key_service,
    get_external_rate_limit_store,
)
from app.api.external.v1.documents import get_external_document_reader
from app.api.external.v1.payments import get_external_payment_reader
from app.api.external.v1.projects import get_external_project_reader
from app.core.config import Settings
from app.core.db import get_db_session
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.api_keys import ApiKey
from app.services.api_keys import ApiKeyService, InMemoryApiKeyRepository, hash_api_key_token

NOW = datetime(2026, 5, 11, 8, 0, tzinfo=UTC)
TOKEN = "mgmt_external_test_token"


class FakeCounterStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.value = 0

    async def increment(self, key: str, ttl_seconds: int) -> int:
        self.calls.append((key, ttl_seconds))
        self.value += 1
        return self.value


class FakeProjectReader:
    async def list_projects(self) -> list[dict[str, object]]:
        return [
            {
                "created_at": NOW,
                "id": uuid4(),
                "name": "Main",
                "project_no": "Z-2026-0001",
                "spent_amount": Decimal("1000.00"),
                "status": "in_progress",
                "total_budget": Decimal("100000.00"),
                "updated_at": NOW,
            },
        ]


class FakePaymentReader:
    async def list_payments(self) -> list[dict[str, object]]:
        return [
            {
                "amount": Decimal("1200.00"),
                "created_at": NOW,
                "id": uuid4(),
                "payment_date": date(2026, 5, 10),
                "payment_no": "PAY-001",
                "payment_type": "normal",
                "sub_project_id": uuid4(),
                "updated_at": NOW,
            },
        ]


class FakeDocumentReader:
    async def list_documents(self) -> list[dict[str, object]]:
        return [
            {
                "created_at": NOW,
                "doc_no": "DOC-001",
                "doc_type": "contract",
                "file_name": "contract.pdf",
                "file_size": 1024,
                "id": uuid4(),
                "is_latest": True,
                "scan_status": "clean",
                "sub_project_id": uuid4(),
                "updated_at": NOW,
                "version": 1,
            },
        ]


def build_client(
    *,
    permissions: list[str] | None = None,
    rate_store: InMemoryExternalApiRateLimitStore | None = None,
) -> TestClient:
    api_key = ApiKey(
        id=uuid4(),
        name="External",
        key_prefix="mgmt_externa",
        key_hash=hash_api_key_token(TOKEN),
        permissions=permissions or ["projects:read", "payments:read", "documents:read"],
        expires_at=NOW + timedelta(days=1),
        last_used_at=None,
        revoked_at=None,
        created_by_id=uuid4(),
        created_at=NOW,
        updated_at=NOW,
    )
    service = ApiKeyService(
        repository=InMemoryApiKeyRepository([api_key]),
        now_provider=lambda: NOW,
    )
    store = rate_store or InMemoryExternalApiRateLimitStore(now_provider=lambda: NOW)

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_api_key_service() -> ApiKeyService:
        return service

    async def fake_rate_store() -> InMemoryExternalApiRateLimitStore:
        return store

    app = create_app(
        settings=Settings(rate_limit_per_minute=2000),
        rate_limit_store=InMemoryRateLimitStore(),
    )
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_external_api_key_service] = fake_api_key_service
    app.dependency_overrides[get_external_rate_limit_store] = fake_rate_store
    app.dependency_overrides[get_external_project_reader] = lambda: FakeProjectReader()
    app.dependency_overrides[get_external_payment_reader] = lambda: FakePaymentReader()
    app.dependency_overrides[get_external_document_reader] = lambda: FakeDocumentReader()
    return TestClient(app)


def test_external_api_rejects_missing_key() -> None:
    client = build_client()

    response = client.get("/api/external/v1/projects")

    assert response.status_code == 401


def test_external_api_rejects_insufficient_permission() -> None:
    client = build_client(permissions=["payments:read"])

    response = client.get("/api/external/v1/projects", headers={"X-API-Key": TOKEN})

    assert response.status_code == 403


def test_external_api_returns_readonly_payloads_without_internal_fields() -> None:
    client = build_client()

    project_response = client.get("/api/external/v1/projects", headers={"X-API-Key": TOKEN})
    payment_response = client.get("/api/external/v1/payments", headers={"X-API-Key": TOKEN})
    document_response = client.get("/api/external/v1/documents", headers={"X-API-Key": TOKEN})

    assert project_response.status_code == 200
    assert project_response.json()["data"]["items"][0]["project_no"] == "Z-2026-0001"
    assert "creator_id" not in project_response.json()["data"]["items"][0]
    assert "dept_id" not in project_response.json()["data"]["items"][0]
    assert payment_response.status_code == 200
    assert payment_response.json()["data"]["items"][0]["payment_no"] == "PAY-001"
    assert "operator_id" not in payment_response.json()["data"]["items"][0]
    assert "remark" not in payment_response.json()["data"]["items"][0]
    assert document_response.status_code == 200
    assert document_response.json()["data"]["items"][0]["doc_no"] == "DOC-001"
    assert "file_path" not in document_response.json()["data"]["items"][0]
    assert "uploader_id" not in document_response.json()["data"]["items"][0]


def test_external_api_rate_limits_1000_requests_per_hour() -> None:
    client = build_client()

    for _ in range(1000):
        response = client.get("/api/external/v1/projects", headers={"X-API-Key": TOKEN})
        assert response.status_code == 200

    response = client.get("/api/external/v1/projects", headers={"X-API-Key": TOKEN})

    assert response.status_code == 429


async def test_redis_external_rate_limit_store_uses_hourly_api_key_bucket() -> None:
    api_key_id = uuid4()
    counter = FakeCounterStore()
    store = RedisExternalApiRateLimitStore(
        counter_store=counter,
        now_provider=lambda: NOW,
    )

    await store.hit(api_key_id=api_key_id)

    assert counter.calls == [(f"external_api:{api_key_id}:2026051108", 3600)]
