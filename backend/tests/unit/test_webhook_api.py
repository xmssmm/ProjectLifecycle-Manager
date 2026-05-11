from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.v1.webhooks import get_webhook_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.users import User, UserRole, UserStatus
from app.models.webhooks import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint
from app.services.webhooks import (
    WebhookDeliveryPage,
    WebhookEndpointPage,
    WebhookEventType,
    build_webhook_delivery,
)

NOW = datetime(2026, 5, 11, 8, 0, tzinfo=UTC)


def make_admin() -> User:
    return User(
        id=uuid4(),
        username="admin",
        email="admin@example.local",
        password_hash="hashed",
        role=UserRole.admin,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=NOW,
        last_login_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_endpoint(admin: User) -> WebhookEndpoint:
    return WebhookEndpoint(
        id=uuid4(),
        name="ERP",
        url="https://erp.example.local/webhook",
        secret="top-secret",
        event_types=[WebhookEventType.payment_created.value],
        is_active=True,
        created_by_id=admin.id,
        created_at=NOW,
        updated_at=NOW,
    )


def make_dead_letter(endpoint: WebhookEndpoint) -> WebhookDelivery:
    delivery = build_webhook_delivery(
        endpoint=endpoint,
        event_id=uuid4(),
        event_type=WebhookEventType.payment_created,
        source_id="payment-1",
        payload={"amount": "1200.00"},
        now=NOW,
        attempt_count=6,
        max_attempts=6,
    )
    delivery.status = WebhookDeliveryStatus.dead_letter
    delivery.last_error = "Webhook returned 500: server error"
    delivery.next_retry_at = None
    return delivery


def build_client() -> tuple[TestClient, WebhookEndpoint, WebhookDelivery]:
    admin = make_admin()
    endpoint = make_endpoint(admin)
    delivery = make_dead_letter(endpoint)

    class FakeWebhookService:
        async def list_endpoints(self, *, page: int, page_size: int) -> WebhookEndpointPage:
            assert page == 1
            assert page_size == 20
            return WebhookEndpointPage(items=[endpoint], page=page, page_size=page_size, total=1)

        async def create_endpoint(
            self,
            *,
            actor: User,
            name: str,
            url: str,
            secret: str,
            event_types: list[str],
        ) -> WebhookEndpoint:
            assert actor.id == admin.id
            assert secret == "new-secret"
            endpoint.name = name
            endpoint.url = url
            endpoint.event_types = event_types
            return endpoint

        async def set_endpoint_active(
            self,
            *,
            endpoint_id: UUID,
            is_active: bool,
        ) -> WebhookEndpoint:
            assert endpoint_id == endpoint.id
            endpoint.is_active = is_active
            return endpoint

        async def list_dead_letters(self, *, page: int, page_size: int) -> WebhookDeliveryPage:
            return WebhookDeliveryPage(items=[delivery], page=page, page_size=page_size, total=1)

        async def replay_dead_letter(self, *, delivery_id: UUID) -> WebhookDelivery:
            assert delivery_id == delivery.id
            delivery.status = WebhookDeliveryStatus.pending
            delivery.attempt_count = 0
            return delivery

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return admin

    async def fake_service() -> FakeWebhookService:
        return FakeWebhookService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_webhook_service] = fake_service
    return TestClient(app), endpoint, delivery


def test_admin_webhook_endpoints_do_not_return_secret() -> None:
    client, endpoint, _delivery = build_client()

    create_response = client.post(
        "/api/v1/webhooks",
        json={
            "event_types": [WebhookEventType.payment_created.value],
            "name": "ERP",
            "secret": "new-secret",
            "url": "https://erp.example.local/webhook",
        },
    )
    list_response = client.get("/api/v1/webhooks")
    disable_response = client.patch(f"/api/v1/webhooks/{endpoint.id}/active", json=False)

    assert create_response.status_code == 200
    assert create_response.json()["data"]["secret_set"] is True
    assert "secret" not in create_response.json()["data"]
    assert list_response.status_code == 200
    assert "secret" not in list_response.json()["data"]["items"][0]
    assert disable_response.status_code == 200
    assert disable_response.json()["data"]["is_active"] is False


def test_admin_can_query_and_replay_webhook_dead_letters() -> None:
    client, _endpoint, delivery = build_client()

    list_response = client.get("/api/v1/webhooks/dead-letters")
    replay_response = client.post(f"/api/v1/webhooks/deliveries/{delivery.id}/replay")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["status"] == "dead_letter"
    assert list_response.json()["data"]["items"][0]["last_error"] == (
        "Webhook returned 500: server error"
    )
    assert replay_response.status_code == 200
    assert replay_response.json()["data"]["status"] == "pending"
