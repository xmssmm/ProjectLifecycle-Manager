from uuid import UUID

from pydantic import BaseModel, Field

from app.models.users import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenPairRead(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserRead(BaseModel):
    id: UUID
    username: str
    role: UserRole
    dept_id: UUID | None
