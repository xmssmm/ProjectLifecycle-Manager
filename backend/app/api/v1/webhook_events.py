from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.webhooks import SqlAlchemyWebhookRepository, WebhookEventType, WebhookService


async def enqueue_webhook_event(
    *,
    event_type: WebhookEventType,
    payload: dict[str, object],
    session: AsyncSession,
    source_id: UUID | str,
) -> None:
    if not isinstance(session, AsyncSession):
        return
    service = WebhookService(repository=SqlAlchemyWebhookRepository(session))
    await service.enqueue_event(
        event_type=event_type,
        source_id=str(source_id),
        payload=payload,
    )
