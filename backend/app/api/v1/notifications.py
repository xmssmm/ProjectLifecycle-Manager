from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.notifications import Notification
from app.models.users import User
from app.schemas.notifications import (
    NotificationListRead,
    NotificationPreferenceListRead,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
    NotificationReadAllResult,
    NotificationUnreadCountRead,
)
from app.services.notifications import (
    NotificationDeliveryMode,
    NotificationPage,
    NotificationPreferenceState,
    NotificationService,
    SqlAlchemyNotificationRepository,
    StoredNotificationPreference,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def get_notification_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NotificationService:
    return NotificationService(repository=SqlAlchemyNotificationRepository(session))


def serialize_notification(notification: Notification) -> dict[str, object]:
    return NotificationRead.model_validate(notification).model_dump(mode="json")


def serialize_notification_page(page: NotificationPage) -> dict[str, object]:
    payload = NotificationListRead(
        items=[NotificationRead.model_validate(notification) for notification in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
    )
    return payload.model_dump(mode="json")


def serialize_notification_preferences(
    preferences: list[NotificationPreferenceState],
) -> dict[str, object]:
    payload = NotificationPreferenceListRead(
        items=[
            NotificationPreferenceRead(
                scenario=preference.scenario,
                label=preference.label,
                description=preference.description,
                direct_related=preference.direct_related,
                enabled=preference.enabled,
                delivery_mode=preference.delivery_mode.value,
            )
            for preference in preferences
        ],
    )
    return payload.model_dump(mode="json")


@router.get("")
async def list_notifications(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    unread: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    notification_page = await service.list_notifications(
        actor=current_user,
        page=page,
        page_size=page_size,
        unread=unread,
    )
    return success_response(serialize_notification_page(notification_page))


@router.get("/preferences")
async def list_notification_preferences(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    preferences = await service.list_preferences(actor=current_user)
    return success_response(serialize_notification_preferences(preferences))


@router.put("/preferences")
async def update_notification_preferences(
    payload: NotificationPreferenceUpdate,
    service: Annotated[NotificationService, Depends(get_notification_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    preferences = await service.update_preferences(
        actor=current_user,
        preferences={
            item.scenario: StoredNotificationPreference(
                enabled=item.enabled,
                delivery_mode=NotificationDeliveryMode(item.delivery_mode),
            )
            for item in payload.preferences
        },
    )
    return success_response(serialize_notification_preferences(preferences))


@router.get("/unread-count")
async def unread_count(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    payload = NotificationUnreadCountRead(count=await service.unread_count(actor=current_user))
    return success_response(payload.model_dump(mode="json"))


@router.post("/read-all")
async def read_all_notifications(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    payload = NotificationReadAllResult(
        read_count=await service.mark_all_read(actor=current_user),
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("/{notification_id}/read")
async def read_notification(
    notification_id: UUID,
    service: Annotated[NotificationService, Depends(get_notification_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    notification = await service.mark_read(actor=current_user, notification_id=notification_id)
    return success_response(serialize_notification(notification))
