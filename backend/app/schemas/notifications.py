from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

NotificationDeliveryModeValue = Literal["real_time", "daily_digest"]
NotificationChannelValue = Literal["in_app", "email", "wework", "dingtalk"]


class NotificationChannelSettings(BaseModel):
    in_app: bool = True
    email: bool = False
    wework: bool = False
    dingtalk: bool = False


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
    channels: NotificationChannelSettings


class NotificationPreferenceListRead(BaseModel):
    items: list[NotificationPreferenceRead]


class NotificationPreferenceUpdateItem(BaseModel):
    scenario: str
    enabled: bool
    delivery_mode: NotificationDeliveryModeValue = "real_time"
    channels: NotificationChannelSettings | None = None


class NotificationPreferenceUpdate(BaseModel):
    preferences: list[NotificationPreferenceUpdateItem]
