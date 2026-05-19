from pydantic import BaseModel, Field

from app.models.users import UserRole


class RolePermissionOptionRead(BaseModel):
    code: str
    label: str


class RolePermissionRead(BaseModel):
    role: UserRole
    permission_codes: list[str]


class RolePermissionMatrixRead(BaseModel):
    permissions: list[RolePermissionOptionRead]
    items: list[RolePermissionRead]


class RolePermissionUpdate(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)
