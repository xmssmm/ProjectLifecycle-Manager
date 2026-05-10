from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    id: UUID
    actor_id: UUID | None
    action: str
    target_type: str
    target_id: str
    before_state: dict[str, object]
    after_state: dict[str, object]
    ip_address: str | None
    user_agent: str | None
    extra: dict[str, object]
    request_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListRead(BaseModel):
    items: list[AuditLogRead]
    page: int
    page_size: int
    total: int
