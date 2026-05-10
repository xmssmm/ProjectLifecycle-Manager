from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OAuthBindingRead(BaseModel):
    id: UUID
    user_id: UUID
    provider: str
    external_id: str
    email: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OAuthAuthorizationStartRead(BaseModel):
    authorization_url: str
    state: str
