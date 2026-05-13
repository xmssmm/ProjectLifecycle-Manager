from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.exceptions import PermissionDeniedError
from app.core.permissions import require_permission, require_role, user_has_permission
from app.models.users import User, UserRole, UserStatus


def make_user(role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=role.value,
        email=None,
        password_hash="hash",
        role=role,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_require_role_accepts_string_role_and_returns_user() -> None:
    user = make_user(UserRole.admin)
    dependency = require_role("admin")

    assert await dependency(user) is user


@pytest.mark.asyncio
async def test_require_role_rejects_unlisted_role() -> None:
    user = make_user(UserRole.proj_member)
    dependency = require_role("admin")

    with pytest.raises(PermissionDeniedError):
        await dependency(user)


@pytest.mark.parametrize(
    ("role", "permission"),
    [
        (UserRole.admin, "payment.create"),
        (UserRole.dept_manager, "user.manage"),
        (UserRole.finance_manager, "main_project.create"),
        (UserRole.proj_leader, "payment.create"),
        (UserRole.proj_member, "task.assign"),
    ],
)
def test_permission_matrix_rejects_key_denied_paths(role: UserRole, permission: str) -> None:
    assert not user_has_permission(make_user(role), permission)


@pytest.mark.parametrize(
    ("role", "permission"),
    [
        (UserRole.admin, "user.manage"),
        (UserRole.dept_manager, "main_project.create"),
        (UserRole.finance_manager, "payment.create"),
        (UserRole.proj_leader, "phase.promote"),
        (UserRole.proj_member, "phase.promote"),
        (UserRole.proj_member, "document.upload"),
    ],
)
def test_permission_matrix_allows_key_granted_paths(role: UserRole, permission: str) -> None:
    assert user_has_permission(make_user(role), permission)


@pytest.mark.asyncio
async def test_require_permission_rejects_missing_permission() -> None:
    user = make_user(UserRole.proj_member)
    dependency = require_permission("task.assign")

    with pytest.raises(PermissionDeniedError):
        await dependency(user)


@pytest.mark.asyncio
async def test_require_permission_accepts_resource_id_param_argument() -> None:
    user = make_user(UserRole.proj_leader)
    dependency = require_permission("project.view_own", resource_id_param="id")

    assert await dependency(user) is user
