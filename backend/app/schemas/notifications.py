from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    id: UUID
    receiver_id: UUID
    scenario: str
    source_id: str
    payload: dict[str, object]
    dedup_key: str
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


class NotificationPreferenceListRead(BaseModel):
    items: list[NotificationPreferenceRead]


class NotificationPreferenceUpdateItem(BaseModel):
    scenario: str
    enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    preferences: list[NotificationPreferenceUpdateItem]
