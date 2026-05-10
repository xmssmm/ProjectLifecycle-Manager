from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)


class DepartmentUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class DepartmentRead(BaseModel):
    id: UUID
    code: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
