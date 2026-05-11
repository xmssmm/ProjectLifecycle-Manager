from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.webhooks import WebhookDeliveryStatus
from app.services.webhooks import WebhookEventType

WebhookName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
WebhookUrl = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
WebhookSecret = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

WEBHOOK_EVENT_TYPES = frozenset(item.value for item in WebhookEventType)


class WebhookEndpointCreate(BaseModel):
    name: WebhookName
    url: WebhookUrl
    secret: WebhookSecret
    event_types: list[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class WebhookEndpointRead(BaseModel):
    id: UUID
    name: str
    url: str
    event_types: list[str]
    is_active: bool
    secret_set: bool
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class WebhookEndpointListRead(BaseModel):
    items: list[WebhookEndpointRead]
    total: int
    page: int
    page_size: int


class WebhookDeliveryRead(BaseModel):
    id: UUID
    endpoint_id: UUID
    event_id: UUID
    event_type: str
    source_id: str
    payload: dict[str, object]
    status: WebhookDeliveryStatus
    attempt_count: int
    max_attempts: int
    last_error: str | None
    response_status: int | None
    next_retry_at: datetime | None
    last_attempt_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookDeliveryListRead(BaseModel):
    items: list[WebhookDeliveryRead]
    total: int
    page: int
    page_size: int
