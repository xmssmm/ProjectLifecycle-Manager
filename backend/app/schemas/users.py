from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.users import UserRole, UserStatus


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1)
    role: UserRole
    email: str | None = Field(default=None, max_length=255)
    dept_id: UUID | None = None


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    dept_id: UUID | None = None


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=1)


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class UserRead(BaseModel):
    id: UUID
    username: str
    email: str | None
    role: UserRole
    dept_id: UUID | None
    status: UserStatus
    password_changed_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListRead(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int
