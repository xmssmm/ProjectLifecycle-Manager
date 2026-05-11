from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

API_KEY_PERMISSIONS = frozenset({"projects:read", "payments:read", "documents:read"})

NameText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ApiKeyCreate(BaseModel):
    name: NameText
    permissions: list[str] = Field(min_length=1)
    expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class ApiKeyRead(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    permissions: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreateRead(BaseModel):
    api_key: ApiKeyRead
    token: str


class ApiKeyListRead(BaseModel):
    items: list[ApiKeyRead]
    total: int
    page: int
    page_size: int
