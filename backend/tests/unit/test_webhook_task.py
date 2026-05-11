from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.models.webhooks import WebhookDeliveryStatus
from app.services.webhooks import (
    InMemoryWebhookRepository,
    WebhookEventType,
    WebhookService,
    WebhookTransportResult,
    build_webhook_delivery,
)
from app.tasks.task_names import WEBHOOK_DELIVERY_RETRY_TASK_NAME
from app.tasks.webhooks import process_webhook_deliveries, retry_webhook_deliveries
from tests.unit.test_webhook_service import RecordingWebhookTransport, make_endpoint

NOW = datetime(2026, 5, 11, 8, 0, tzinfo=UTC)
EVENT_ID = UUID("00000000-0000-0000-0000-000000000456")


@pytest.mark.asyncio
async def test_process_webhook_deliveries_task_helper_processes_due_items() -> None:
    endpoint = make_endpoint()
    delivery = build_webhook_delivery(
        endpoint=endpoint,
        event_id=EVENT_ID,
        event_type=WebhookEventType.project_status_changed,
        source_id="project-1",
        payload={"status": "approved"},
        now=NOW,
    )
    repository = InMemoryWebhookRepository(endpoints=[endpoint], deliveries=[delivery])
    service = WebhookService(
        repository=repository,
        transport=RecordingWebhookTransport(WebhookTransportResult(200, "ok")),
        now_provider=lambda: NOW,
    )

    result = await process_webhook_deliveries(service=service, limit=5)

    assert result == {"processed": 1, "delivered": 1, "retry_scheduled": 0, "dead_letter": 0}
    assert delivery.status == WebhookDeliveryStatus.delivered


def test_retry_webhook_deliveries_task_uses_stable_task_name() -> None:
    assert retry_webhook_deliveries.name == WEBHOOK_DELIVERY_RETRY_TASK_NAME
