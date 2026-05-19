from __future__ import annotations

from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import role_permissions as role_permission_api
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, business_exception_handler
from app.core.permissions import (
    DEFAULT_PERMISSION_MATRIX,
    get_role_permission_service,
    require_permission,
)
from app.core.responses import success_response
from app.models.role_permissions import RolePermission
from app.models.users import User, UserRole, UserStatus
from app.services.role_permissions import InMemoryRolePermissionRepository, RolePermissionService

UPLOAD_PERMISSION_DEPENDENCY = require_permission("document.upload")


def make_user(role: UserRole = UserRole.admin) -> User:
    return User(
        id=uuid4(),
        username=f"{role.value}-{uuid4().hex[:6]}",
        email=None,
        password_hash="hashed",
        role=role,
        dept_id=None,
        status=UserStatus.active,
    )


@pytest.mark.asyncio
async def test_role_permission_service_uses_defaults_until_admin_saves_override() -> None:
    repository = InMemoryRolePermissionRepository()
    service = RolePermissionService(repository=repository)

    defaults = await service.effective_permissions(UserRole.proj_member)
    assert "document.upload" in defaults

    updated = await service.update_role_permissions(
        actor=make_user(UserRole.admin),
        role=UserRole.proj_member,
        permission_codes=["project.view_own"],
    )

    assert updated.role == UserRole.proj_member
    assert updated.permission_codes == ["project.view_own"]
    assert await service.has_permission(UserRole.proj_member, "document.upload") is False
    assert await service.has_permission(UserRole.proj_member, "project.view_own") is True


def test_role_permission_api_lists_and_updates_matrix_for_admin() -> None:
    admin = make_user(UserRole.admin)
    service = RolePermissionService(repository=InMemoryRolePermissionRepository())
    app = FastAPI()
    app.include_router(role_permission_api.router, prefix="/api/v1")
    app.dependency_overrides[role_permission_api.get_role_permission_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    list_response = client.get("/api/v1/role-permissions")
    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["role"] == UserRole.admin.value

    update_response = client.put(
        "/api/v1/role-permissions/proj_member",
        json={"permission_codes": ["project.view_own"]},
    )

    assert update_response.status_code == 200
    assert update_response.json()["data"]["permission_codes"] == ["project.view_own"]


def test_require_permission_uses_dynamic_role_permission_dependency() -> None:
    member = make_user(UserRole.proj_member)
    service = RolePermissionService(
        repository=InMemoryRolePermissionRepository(
            permissions=[
                RolePermission(
                    role=UserRole.proj_member,
                    permission_code=code,
                    enabled=code == "project.view_own",
                )
                for code in DEFAULT_PERMISSION_MATRIX
            ],
        ),
    )
    app = FastAPI()
    app.add_exception_handler(BusinessException, business_exception_handler)

    @app.post("/upload")
    async def upload(_user: Annotated[User, Depends(UPLOAD_PERMISSION_DEPENDENCY)]):
        return success_response({"ok": True})

    app.dependency_overrides[get_current_user] = lambda: member
    app.dependency_overrides[get_role_permission_service] = lambda: service
    client = TestClient(app)

    response = client.post("/upload")

    assert response.status_code == 403, response.text
    assert response.json()["message"] == "无权限操作"
