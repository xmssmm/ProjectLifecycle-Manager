from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.models.webhooks import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint
from app.services.webhooks import (
    InMemoryWebhookRepository,
    WebhookEventType,
    WebhookService,
    WebhookTransportResult,
    build_webhook_delivery,
    build_webhook_signature,
    canonical_webhook_body,
)

NOW = datetime(2026, 5, 11, 8, 0, tzinfo=UTC)
EVENT_ID = UUID("00000000-0000-0000-0000-000000000123")


class RecordingWebhookTransport:
    def __init__(
        self,
        *responses: WebhookTransportResult,
        exc: Exception | None = None,
    ) -> None:
        self.responses = list(responses)
        self.exc = exc
        self.calls: list[tuple[str, str, dict[str, str], float]] = []

    async def post(
        self,
        *,
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookTransportResult:
        if self.exc is not None:
            raise self.exc
        self.calls.append((url, body, headers, timeout_seconds))
        return self.responses.pop(0) if self.responses else WebhookTransportResult(204, "")


def make_endpoint(
    *,
    event_types: list[str] | None = None,
    is_active: bool = True,
) -> WebhookEndpoint:
    return WebhookEndpoint(
        id=uuid4(),
        name="ERP",
        url="https://erp.example.local/webhooks/project",
        secret="top-secret",
        event_types=event_types or [WebhookEventType.payment_created.value],
        is_active=is_active,
        created_by_id=uuid4(),
        created_at=NOW,
        updated_at=NOW,
    )


def make_delivery(*, attempt_count: int = 0, max_attempts: int = 6) -> WebhookDelivery:
    return build_webhook_delivery(
        endpoint=make_endpoint(),
        event_id=EVENT_ID,
        event_type=WebhookEventType.payment_created,
        source_id="payment-1",
        payload={"amount": "1200.00"},
        now=NOW,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
    )


def make_service(
    *,
    repository: InMemoryWebhookRepository,
    transport: RecordingWebhookTransport,
) -> WebhookService:
    return WebhookService(
        repository=repository,
        transport=transport,
        event_id_provider=lambda: EVENT_ID,
        now_provider=lambda: NOW,
    )


def test_hmac_signature_is_stable_and_uses_event_timestamp_and_body() -> None:
    body = canonical_webhook_body({"b": 2, "a": 1})

    signature = build_webhook_signature(
        body=body,
        event_id=str(EVENT_ID),
        secret="top-secret",
        timestamp="2026-05-11T08:00:00Z",
    )

    expected = hmac.new(
        b"top-secret",
        f"2026-05-11T08:00:00Z.{EVENT_ID}.{body}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert body == '{"a":1,"b":2}'
    assert signature == f"sha256={expected}"


@pytest.mark.asyncio
async def test_2xx_response_marks_delivery_delivered_with_required_headers() -> None:
    endpoint = make_endpoint()
    repository = InMemoryWebhookRepository(endpoints=[endpoint])
    transport = RecordingWebhookTransport(WebhookTransportResult(204, ""))
    service = make_service(repository=repository, transport=transport)

    deliveries = await service.enqueue_event(
        event_type=WebhookEventType.payment_created,
        source_id="payment-1",
        payload={"amount": "1200.00"},
    )
    result = await service.process_due(limit=10)

    assert result == {"processed": 1, "delivered": 1, "retry_scheduled": 0, "dead_letter": 0}
    assert deliveries[0].status == WebhookDeliveryStatus.delivered
    assert deliveries[0].attempt_count == 1
    url, body, headers, timeout_seconds = transport.calls[0]
    assert url == endpoint.url
    assert body == '{"amount":"1200.00"}'
    assert headers["X-Event-Id"] == str(EVENT_ID)
    assert headers["X-Timestamp"] == "2026-05-11T08:00:00Z"
    assert headers["X-Signature"].startswith("sha256=")
    assert timeout_seconds == 10.0


@pytest.mark.asyncio
async def test_non_2xx_response_schedules_retry_with_exponential_delay() -> None:
    delivery = make_delivery()
    repository = InMemoryWebhookRepository(deliveries=[delivery])
    transport = RecordingWebhookTransport(WebhookTransportResult(500, "server error"))
    service = make_service(repository=repository, transport=transport)

    result = await service.process_due(limit=10)

    assert result == {"processed": 1, "delivered": 0, "retry_scheduled": 1, "dead_letter": 0}
    assert delivery.status == WebhookDeliveryStatus.retry_scheduled
    assert delivery.attempt_count == 1
    assert delivery.last_error == "Webhook returned 500: server error"
    assert delivery.next_retry_at == NOW + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_timeout_schedules_retry() -> None:
    delivery = make_delivery()
    repository = InMemoryWebhookRepository(deliveries=[delivery])
    transport = RecordingWebhookTransport(exc=TimeoutError("request timed out"))
    service = make_service(repository=repository, transport=transport)

    await service.process_due(limit=10)

    assert delivery.status == WebhookDeliveryStatus.retry_scheduled
    assert delivery.attempt_count == 1
    assert delivery.last_error == "request timed out"


@pytest.mark.asyncio
async def test_reaching_attempt_limit_moves_delivery_to_dead_letter() -> None:
    delivery = make_delivery(attempt_count=5, max_attempts=6)
    repository = InMemoryWebhookRepository(deliveries=[delivery])
    transport = RecordingWebhookTransport(WebhookTransportResult(503, "unavailable"))
    service = make_service(repository=repository, transport=transport)

    result = await service.process_due(limit=10)

    assert result == {"processed": 1, "delivered": 0, "retry_scheduled": 0, "dead_letter": 1}
    assert delivery.status == WebhookDeliveryStatus.dead_letter
    assert delivery.attempt_count == 6
    assert delivery.next_retry_at is None
