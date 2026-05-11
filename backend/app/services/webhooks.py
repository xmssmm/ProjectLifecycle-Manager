from __future__ import annotations

import asyncio
import enum
import hashlib
import hmac
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ResourceNotFoundError, ValidationFailedError
from app.models.users import User
from app.models.webhooks import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint

DEFAULT_WEBHOOK_MAX_ATTEMPTS = 6
DEFAULT_WEBHOOK_RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
)
DEFAULT_WEBHOOK_TIMEOUT_SECONDS = 10.0


class WebhookEventType(enum.StrEnum):
    project_status_changed = "project.status_changed"
    payment_created = "payment.created"
    phase_promoted = "phase.promoted"
    revoke_request_reviewed = "revoke_request.reviewed"


@dataclass(frozen=True)
class WebhookEndpointPage:
    items: list[WebhookEndpoint]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class WebhookDeliveryPage:
    items: list[WebhookDelivery]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class WebhookTransportResult:
    status_code: int
    text: str


class WebhookTransport(Protocol):
    async def post(
        self,
        *,
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookTransportResult:
        ...


class UrllibWebhookTransport:
    async def post(
        self,
        *,
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookTransportResult:
        return await asyncio.to_thread(
            self._post_sync,
            url,
            body,
            headers,
            timeout_seconds,
        )

    @staticmethod
    def _post_sync(
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookTransportResult:
        request = Request(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                text = response.read().decode("utf-8", errors="replace")
                return WebhookTransportResult(status_code=response.status, text=text)
        except HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            return WebhookTransportResult(status_code=exc.code, text=text)
        except TimeoutError:
            raise
        except URLError as exc:
            return WebhookTransportResult(status_code=0, text=str(exc.reason))


class WebhookRepository(Protocol):
    def add_endpoint(self, endpoint: WebhookEndpoint) -> None:
        ...

    def add_delivery(self, delivery: WebhookDelivery) -> None:
        ...

    async def list_endpoints(self, *, page: int, page_size: int) -> WebhookEndpointPage:
        ...

    async def get_endpoint_for_update(self, endpoint_id: UUID) -> WebhookEndpoint | None:
        ...

    async def list_active_endpoints_for_event(self, event_type: str) -> list[WebhookEndpoint]:
        ...

    async def list_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[WebhookDelivery]:
        ...

    async def list_dead_letters(self, *, page: int, page_size: int) -> WebhookDeliveryPage:
        ...

    async def get_delivery_for_update(self, delivery_id: UUID) -> WebhookDelivery | None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_endpoint(self, endpoint: WebhookEndpoint) -> None:
        ...

    async def refresh_delivery(self, delivery: WebhookDelivery) -> None:
        ...


class SqlAlchemyWebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_endpoint(self, endpoint: WebhookEndpoint) -> None:
        self._session.add(endpoint)

    def add_delivery(self, delivery: WebhookDelivery) -> None:
        self._session.add(delivery)

    async def list_endpoints(self, *, page: int, page_size: int) -> WebhookEndpointPage:
        total = await self._session.scalar(select(func.count()).select_from(WebhookEndpoint))
        result = await self._session.scalars(
            select(WebhookEndpoint)
            .order_by(WebhookEndpoint.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
        return WebhookEndpointPage(
            items=list(result.all()),
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )

    async def get_endpoint_for_update(self, endpoint_id: UUID) -> WebhookEndpoint | None:
        endpoint = await self._session.scalar(
            select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id).with_for_update(),
        )
        return endpoint if isinstance(endpoint, WebhookEndpoint) else None

    async def list_active_endpoints_for_event(self, event_type: str) -> list[WebhookEndpoint]:
        result = await self._session.scalars(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.is_active.is_(True))
            .order_by(WebhookEndpoint.created_at.asc()),
        )
        return [endpoint for endpoint in result.all() if event_type in endpoint.event_types]

    async def list_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[WebhookDelivery]:
        result = await self._session.scalars(
            select(WebhookDelivery)
            .options(selectinload(WebhookDelivery.endpoint))
            .where(
                WebhookDelivery.status.in_(
                    [
                        WebhookDeliveryStatus.pending,
                        WebhookDeliveryStatus.retry_scheduled,
                    ],
                ),
                WebhookDelivery.next_retry_at <= now,
            )
            .order_by(WebhookDelivery.next_retry_at, WebhookDelivery.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True),
        )
        return list(result.all())

    async def list_dead_letters(self, *, page: int, page_size: int) -> WebhookDeliveryPage:
        total = await self._session.scalar(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.status == WebhookDeliveryStatus.dead_letter),
        )
        result = await self._session.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.status == WebhookDeliveryStatus.dead_letter)
            .order_by(WebhookDelivery.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
        return WebhookDeliveryPage(
            items=list(result.all()),
            page=page,
            page_size=page_size,
            total=int(total or 0),
        )

    async def get_delivery_for_update(self, delivery_id: UUID) -> WebhookDelivery | None:
        delivery = await self._session.scalar(
            select(WebhookDelivery).where(WebhookDelivery.id == delivery_id).with_for_update(),
        )
        return delivery if isinstance(delivery, WebhookDelivery) else None

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_endpoint(self, endpoint: WebhookEndpoint) -> None:
        await self._session.refresh(endpoint)

    async def refresh_delivery(self, delivery: WebhookDelivery) -> None:
        await self._session.refresh(delivery)


class InMemoryWebhookRepository:
    def __init__(
        self,
        *,
        deliveries: Sequence[WebhookDelivery] | None = None,
        endpoints: Sequence[WebhookEndpoint] | None = None,
    ) -> None:
        self.deliveries = list(deliveries or [])
        self.endpoints = list(endpoints or [])

    def add_endpoint(self, endpoint: WebhookEndpoint) -> None:
        self.endpoints.append(endpoint)

    def add_delivery(self, delivery: WebhookDelivery) -> None:
        self.deliveries.append(delivery)

    async def list_endpoints(self, *, page: int, page_size: int) -> WebhookEndpointPage:
        endpoints = sorted(self.endpoints, key=lambda item: item.created_at, reverse=True)
        start = (page - 1) * page_size
        return WebhookEndpointPage(
            items=endpoints[start : start + page_size],
            page=page,
            page_size=page_size,
            total=len(endpoints),
        )

    async def get_endpoint_for_update(self, endpoint_id: UUID) -> WebhookEndpoint | None:
        return next((endpoint for endpoint in self.endpoints if endpoint.id == endpoint_id), None)

    async def list_active_endpoints_for_event(self, event_type: str) -> list[WebhookEndpoint]:
        return [
            endpoint
            for endpoint in self.endpoints
            if endpoint.is_active and event_type in endpoint.event_types
        ]

    async def list_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[WebhookDelivery]:
        due = [
            delivery
            for delivery in self.deliveries
            if delivery.status
            in {
                WebhookDeliveryStatus.pending,
                WebhookDeliveryStatus.retry_scheduled,
            }
            and delivery.next_retry_at is not None
            and delivery.next_retry_at <= now
        ]
        return sorted(due, key=lambda item: (item.next_retry_at, item.created_at))[:limit]

    async def list_dead_letters(self, *, page: int, page_size: int) -> WebhookDeliveryPage:
        deliveries = [
            delivery
            for delivery in self.deliveries
            if delivery.status == WebhookDeliveryStatus.dead_letter
        ]
        deliveries = sorted(deliveries, key=lambda item: item.updated_at, reverse=True)
        start = (page - 1) * page_size
        return WebhookDeliveryPage(
            items=deliveries[start : start + page_size],
            page=page,
            page_size=page_size,
            total=len(deliveries),
        )

    async def get_delivery_for_update(self, delivery_id: UUID) -> WebhookDelivery | None:
        return next((delivery for delivery in self.deliveries if delivery.id == delivery_id), None)

    async def commit(self) -> None:
        return None

    async def refresh_endpoint(self, endpoint: WebhookEndpoint) -> None:
        _ = endpoint
        return None

    async def refresh_delivery(self, delivery: WebhookDelivery) -> None:
        _ = delivery
        return None


class WebhookService:
    def __init__(
        self,
        *,
        repository: WebhookRepository,
        transport: WebhookTransport | None = None,
        event_id_provider: Callable[[], UUID] = uuid4,
        now_provider: Callable[[], datetime] | None = None,
        retry_delays: Sequence[timedelta] = DEFAULT_WEBHOOK_RETRY_DELAYS,
        timeout_seconds: float = DEFAULT_WEBHOOK_TIMEOUT_SECONDS,
    ) -> None:
        self._repository = repository
        self._transport = transport or UrllibWebhookTransport()
        self._event_id_provider = event_id_provider
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._retry_delays = tuple(retry_delays)
        self._timeout_seconds = timeout_seconds

    async def list_endpoints(self, *, page: int = 1, page_size: int = 20) -> WebhookEndpointPage:
        page, page_size = self._clean_page(page=page, page_size=page_size)
        return await self._repository.list_endpoints(page=page, page_size=page_size)

    async def create_endpoint(
        self,
        *,
        actor: User,
        name: str,
        url: str,
        secret: str,
        event_types: Sequence[str],
    ) -> WebhookEndpoint:
        cleaned_event_types = self._clean_event_types(event_types)
        endpoint = WebhookEndpoint(
            id=uuid4(),
            name=self._clean_text(name, "Webhook name is required", max_length=120),
            url=self._clean_url(url),
            secret=self._clean_text(secret, "Webhook secret is required", max_length=255),
            event_types=cleaned_event_types,
            is_active=True,
            created_by_id=actor.id,
            created_at=self._now_provider(),
            updated_at=self._now_provider(),
        )
        self._repository.add_endpoint(endpoint)
        await self._repository.commit()
        await self._repository.refresh_endpoint(endpoint)
        return endpoint

    async def set_endpoint_active(self, *, endpoint_id: UUID, is_active: bool) -> WebhookEndpoint:
        endpoint = await self._repository.get_endpoint_for_update(endpoint_id)
        if endpoint is None:
            raise ResourceNotFoundError("Webhook endpoint does not exist")
        endpoint.is_active = is_active
        endpoint.updated_at = self._now_provider()
        await self._repository.commit()
        await self._repository.refresh_endpoint(endpoint)
        return endpoint

    async def enqueue_event(
        self,
        *,
        event_type: WebhookEventType,
        source_id: str,
        payload: dict[str, object],
    ) -> list[WebhookDelivery]:
        now = self._now_provider()
        event_id = self._event_id_provider()
        endpoints = await self._repository.list_active_endpoints_for_event(event_type.value)
        deliveries = [
            build_webhook_delivery(
                endpoint=endpoint,
                event_id=event_id,
                event_type=event_type,
                source_id=source_id,
                payload=payload,
                now=now,
            )
            for endpoint in endpoints
        ]
        for delivery in deliveries:
            self._repository.add_delivery(delivery)
        await self._repository.commit()
        return deliveries

    async def process_due(self, *, limit: int = 100) -> dict[str, int]:
        now = self._now_provider()
        deliveries = await self._repository.list_due_deliveries(now=now, limit=limit)
        result = {"processed": 0, "delivered": 0, "retry_scheduled": 0, "dead_letter": 0}
        for delivery in deliveries:
            await self.attempt_delivery(delivery=delivery)
            result["processed"] += 1
            if delivery.status == WebhookDeliveryStatus.delivered:
                result["delivered"] += 1
            elif delivery.status == WebhookDeliveryStatus.retry_scheduled:
                result["retry_scheduled"] += 1
            elif delivery.status == WebhookDeliveryStatus.dead_letter:
                result["dead_letter"] += 1
        return result

    async def attempt_delivery(self, *, delivery: WebhookDelivery) -> None:
        if delivery.status in {WebhookDeliveryStatus.delivered, WebhookDeliveryStatus.dead_letter}:
            return

        body = canonical_webhook_body(delivery.payload)
        timestamp = format_webhook_timestamp(self._now_provider())
        headers = build_webhook_headers(
            body=body,
            delivery=delivery,
            timestamp=timestamp,
        )
        try:
            response = await self._transport.post(
                url=delivery.endpoint.url,
                body=body,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
            )
        except TimeoutError:
            await self.mark_failed_attempt(delivery=delivery, error="request timed out")
            return
        except Exception as exc:  # noqa: BLE001
            await self.mark_failed_attempt(delivery=delivery, error=str(exc))
            return

        if 200 <= response.status_code < 300:
            await self.mark_delivered(delivery=delivery, response_status=response.status_code)
            return
        error = f"Webhook returned {response.status_code}: {response.text}"
        await self.mark_failed_attempt(
            delivery=delivery,
            error=error,
            response_status=response.status_code,
        )

    async def mark_delivered(self, *, delivery: WebhookDelivery, response_status: int) -> None:
        now = self._now_provider()
        delivery.attempt_count += 1
        delivery.status = WebhookDeliveryStatus.delivered
        delivery.last_error = None
        delivery.response_status = response_status
        delivery.next_retry_at = None
        delivery.last_attempt_at = now
        delivery.delivered_at = now
        delivery.updated_at = now
        await self._repository.commit()

    async def mark_failed_attempt(
        self,
        *,
        delivery: WebhookDelivery,
        error: str,
        response_status: int | None = None,
    ) -> None:
        now = self._now_provider()
        delivery.attempt_count += 1
        delivery.last_error = error
        delivery.response_status = response_status
        delivery.last_attempt_at = now
        delivery.delivered_at = None
        delivery.updated_at = now

        if delivery.attempt_count >= delivery.max_attempts:
            delivery.status = WebhookDeliveryStatus.dead_letter
            delivery.next_retry_at = None
        else:
            delivery.status = WebhookDeliveryStatus.retry_scheduled
            delivery.next_retry_at = self._next_retry_at(
                now=now,
                attempt_count=delivery.attempt_count,
            )
        await self._repository.commit()

    async def list_dead_letters(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> WebhookDeliveryPage:
        page, page_size = self._clean_page(page=page, page_size=page_size)
        return await self._repository.list_dead_letters(page=page, page_size=page_size)

    async def replay_dead_letter(self, *, delivery_id: UUID) -> WebhookDelivery:
        delivery = await self._repository.get_delivery_for_update(delivery_id)
        if delivery is None:
            raise ResourceNotFoundError("Webhook delivery does not exist")
        delivery.status = WebhookDeliveryStatus.pending
        delivery.attempt_count = 0
        delivery.last_error = None
        delivery.response_status = None
        delivery.next_retry_at = self._now_provider()
        delivery.last_attempt_at = None
        delivery.delivered_at = None
        delivery.updated_at = self._now_provider()
        await self._repository.commit()
        await self._repository.refresh_delivery(delivery)
        return delivery

    def _next_retry_at(self, *, now: datetime, attempt_count: int) -> datetime:
        delay_index = min(attempt_count - 1, len(self._retry_delays) - 1)
        return now + self._retry_delays[delay_index]

    @staticmethod
    def _clean_page(*, page: int, page_size: int) -> tuple[int, int]:
        if page < 1:
            raise ValidationFailedError("Page must be greater than zero")
        if page_size < 1 or page_size > 100:
            raise ValidationFailedError("Page size must be between 1 and 100")
        return page, page_size

    @staticmethod
    def _clean_text(value: str, message: str, *, max_length: int) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValidationFailedError(message)
        if len(cleaned) > max_length:
            raise ValidationFailedError(f"Value must be at most {max_length} characters")
        return cleaned

    @classmethod
    def _clean_url(cls, value: str) -> str:
        cleaned = cls._clean_text(value, "Webhook URL is required", max_length=500)
        if not cleaned.startswith(("https://", "http://")):
            raise ValidationFailedError("Webhook URL must use http or https")
        return cleaned

    @staticmethod
    def _clean_event_types(event_types: Sequence[str]) -> list[str]:
        allowed = {item.value for item in WebhookEventType}
        cleaned = [item for item in dict.fromkeys(event_types) if item in allowed]
        if not cleaned:
            raise ValidationFailedError("Webhook must subscribe to at least one event")
        return cleaned


def canonical_webhook_body(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def build_webhook_signature(*, body: str, event_id: str, secret: str, timestamp: str) -> str:
    message = f"{timestamp}.{event_id}.{body}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def format_webhook_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_webhook_headers(
    *,
    body: str,
    delivery: WebhookDelivery,
    timestamp: str,
) -> dict[str, str]:
    event_id = str(delivery.event_id)
    return {
        "Content-Type": "application/json",
        "X-Event-Id": event_id,
        "X-Event-Type": delivery.event_type,
        "X-Signature": build_webhook_signature(
            body=body,
            event_id=event_id,
            secret=delivery.endpoint.secret,
            timestamp=timestamp,
        ),
        "X-Timestamp": timestamp,
    }


def build_webhook_delivery(
    *,
    endpoint: WebhookEndpoint,
    event_id: UUID,
    event_type: WebhookEventType,
    source_id: str,
    payload: dict[str, object],
    now: datetime,
    attempt_count: int = 0,
    max_attempts: int = DEFAULT_WEBHOOK_MAX_ATTEMPTS,
) -> WebhookDelivery:
    status = (
        WebhookDeliveryStatus.pending
        if attempt_count == 0
        else WebhookDeliveryStatus.retry_scheduled
    )
    return WebhookDelivery(
        id=uuid4(),
        endpoint_id=endpoint.id,
        event_id=event_id,
        event_type=event_type.value,
        source_id=source_id,
        payload=dict(payload),
        status=status,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        last_error=None,
        response_status=None,
        next_retry_at=now,
        last_attempt_at=None,
        delivered_at=None,
        created_at=now,
        updated_at=now,
        endpoint=endpoint,
    )
