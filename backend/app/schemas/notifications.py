from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

NotificationDeliveryModeValue = Literal["real_time", "daily_digest"]


class NotificationRead(BaseModel):
    id: UUID
    receiver_id: UUID
    scenario: str
    source_id: str
    payload: dict[str, object]
    dedup_key: str
    delivery_mode: NotificationDeliveryModeValue
    digest_sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListRead(BaseModel):
    items: list[NotificationRead]
    page: int
    page_size: int
    total: int


class NotificationUnreadCountRead(BaseModel):
    count: int


class NotificationReadAllResult(BaseModel):
    read_count: int


class NotificationPreferenceRead(BaseModel):
    scenario: str
    label: str
    description: str
    direct_related: bool
    enabled: bool
    delivery_mode: NotificationDeliveryModeValue


class NotificationPreferenceListRead(BaseModel):
    items: list[NotificationPreferenceRead]


class NotificationPreferenceUpdateItem(BaseModel):
    scenario: str
    enabled: bool
    delivery_mode: NotificationDeliveryModeValue = "real_time"


class NotificationPreferenceUpdate(BaseModel):
    preferences: list[NotificationPreferenceUpdateItem]
