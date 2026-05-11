from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.models.webhooks import WebhookDelivery, WebhookEndpoint
from app.schemas.webhooks import (
    WebhookDeliveryListRead,
    WebhookDeliveryRead,
    WebhookEndpointCreate,
    WebhookEndpointListRead,
    WebhookEndpointRead,
)
from app.services.webhooks import SqlAlchemyWebhookRepository, WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def get_webhook_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WebhookService:
    return WebhookService(repository=SqlAlchemyWebhookRepository(session))


def serialize_endpoint(endpoint: WebhookEndpoint) -> dict[str, object]:
    payload = WebhookEndpointRead(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        event_types=list(endpoint.event_types),
        is_active=endpoint.is_active,
        secret_set=bool(endpoint.secret),
        created_by_id=endpoint.created_by_id,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )
    return payload.model_dump(mode="json")


def serialize_delivery(delivery: WebhookDelivery) -> dict[str, object]:
    return WebhookDeliveryRead.model_validate(delivery).model_dump(mode="json")


@router.get("")
async def list_webhook_endpoints(
    service: Annotated[WebhookService, Depends(get_webhook_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    result = await service.list_endpoints(page=page, page_size=page_size)
    payload = WebhookEndpointListRead(
        items=[
            WebhookEndpointRead(
                id=endpoint.id,
                name=endpoint.name,
                url=endpoint.url,
                event_types=list(endpoint.event_types),
                is_active=endpoint.is_active,
                secret_set=bool(endpoint.secret),
                created_by_id=endpoint.created_by_id,
                created_at=endpoint.created_at,
                updated_at=endpoint.updated_at,
            )
            for endpoint in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def create_webhook_endpoint(
    payload: WebhookEndpointCreate,
    service: Annotated[WebhookService, Depends(get_webhook_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    endpoint = await service.create_endpoint(
        actor=current_user,
        name=payload.name,
        url=payload.url,
        secret=payload.secret,
        event_types=payload.event_types,
    )
    return success_response(serialize_endpoint(endpoint))


@router.patch("/{endpoint_id}/active")
async def set_webhook_endpoint_active(
    endpoint_id: UUID,
    is_active: Annotated[bool, Body()],
    service: Annotated[WebhookService, Depends(get_webhook_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    endpoint = await service.set_endpoint_active(endpoint_id=endpoint_id, is_active=is_active)
    return success_response(serialize_endpoint(endpoint))


@router.get("/dead-letters")
async def list_webhook_dead_letters(
    service: Annotated[WebhookService, Depends(get_webhook_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    result = await service.list_dead_letters(page=page, page_size=page_size)
    payload = WebhookDeliveryListRead(
        items=[WebhookDeliveryRead.model_validate(delivery) for delivery in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("/deliveries/{delivery_id}/replay")
async def replay_webhook_dead_letter(
    delivery_id: UUID,
    service: Annotated[WebhookService, Depends(get_webhook_service)],
    _current_user: Annotated[User, Depends(require_role(UserRole.admin))],
) -> dict[str, object]:
    delivery = await service.replay_dead_letter(delivery_id=delivery_id)
    return success_response(serialize_delivery(delivery))
