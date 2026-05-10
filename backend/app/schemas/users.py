from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.users import UserRole, UserStatus


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
