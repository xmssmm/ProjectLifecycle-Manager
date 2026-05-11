from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.users import DEFAULT_USER_TIMEZONE, UserRole, UserStatus


def validate_timezone(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    try:
        ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Invalid IANA timezone") from exc
    return normalized


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1)
    role: UserRole
    email: str | None = Field(default=None, max_length=255)
    dept_id: UUID | None = None
    sso_required: bool = False
    timezone: str = Field(default=DEFAULT_USER_TIMEZONE, max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_user_timezone(cls, value: str) -> str:
        return validate_timezone(value) or DEFAULT_USER_TIMEZONE


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    dept_id: UUID | None = None
    sso_required: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_user_timezone(cls, value: str | None) -> str | None:
        return validate_timezone(value)


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
    sso_required: bool
    timezone: str
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
