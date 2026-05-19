from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import PermissionDeniedError
from app.models.users import User, UserRole

PermissionDependency = Callable[[User], Awaitable[User]]

DEFAULT_PERMISSION_MATRIX: dict[str, frozenset[UserRole]] = {
    "user.manage": frozenset({UserRole.admin}),
    "system.config": frozenset({UserRole.admin}),
    "audit_log.read": frozenset({UserRole.admin}),
    "database.export": frozenset({UserRole.admin}),
    "role_permission.manage": frozenset({UserRole.admin}),
    "main_project.create": frozenset({UserRole.admin, UserRole.dept_manager}),
    "main_project.edit": frozenset({UserRole.admin, UserRole.dept_manager}),
    "main_project.review": frozenset({UserRole.admin, UserRole.dept_manager}),
    "main_project.close": frozenset({UserRole.admin, UserRole.dept_manager}),
    "project.import": frozenset({UserRole.admin}),
    "sub_project.create": frozenset({UserRole.admin, UserRole.proj_leader}),
    "sub_project.review": frozenset({UserRole.admin, UserRole.dept_manager}),
    "sub_project.terminate": frozenset({UserRole.admin, UserRole.dept_manager}),
    "phase.promote": frozenset({UserRole.admin, UserRole.proj_leader, UserRole.proj_member}),
    "acceptance_step.create": frozenset({UserRole.admin, UserRole.proj_leader}),
    "acceptance_step.complete": frozenset(
        {
            UserRole.admin,
            UserRole.dept_manager,
            UserRole.finance_manager,
            UserRole.proj_leader,
            UserRole.proj_member,
        },
    ),
    "payment.create": frozenset({UserRole.finance_manager}),
    "payment.reverse": frozenset({UserRole.finance_manager}),
    "document.upload": frozenset(
        {
            UserRole.admin,
            UserRole.dept_manager,
            UserRole.finance_manager,
            UserRole.proj_leader,
            UserRole.proj_member,
        },
    ),
    "document.download": frozenset(
        {
            UserRole.admin,
            UserRole.dept_manager,
            UserRole.finance_manager,
            UserRole.proj_leader,
            UserRole.proj_member,
        },
    ),
    "task.assign": frozenset({UserRole.admin, UserRole.proj_leader}),
    "task.complete": frozenset(
        {
            UserRole.admin,
            UserRole.dept_manager,
            UserRole.finance_manager,
            UserRole.proj_leader,
            UserRole.proj_member,
        },
    ),
    "revoke_request.submit": frozenset({UserRole.proj_leader}),
    "revoke_request.review": frozenset({UserRole.admin, UserRole.dept_manager}),
    "report.generate": frozenset(
        {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
    ),
    "project.view_all": frozenset(
        {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
    ),
    "project.view_own": frozenset({UserRole.proj_leader, UserRole.proj_member}),
}
PERMISSION_MATRIX = DEFAULT_PERMISSION_MATRIX


def normalize_role(role: UserRole | str) -> UserRole:
    return role if isinstance(role, UserRole) else UserRole(role)


def user_has_permission(user: User, permission: str) -> bool:
    allowed_roles = DEFAULT_PERMISSION_MATRIX.get(permission)
    return allowed_roles is not None and user.role in allowed_roles


def get_role_permission_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Any:
    from app.services.role_permissions import (  # noqa: PLC0415
        InMemoryRolePermissionRepository,
        RolePermissionService,
        SqlAlchemyRolePermissionRepository,
    )

    if not hasattr(session, "scalars"):
        return RolePermissionService(repository=InMemoryRolePermissionRepository())
    return RolePermissionService(repository=SqlAlchemyRolePermissionRepository(session))


ROLE_PERMISSION_SERVICE_DEPENDENCY = Depends(get_role_permission_service)


def require_role(*roles: UserRole | str) -> PermissionDependency:
    allowed_roles = frozenset(normalize_role(role) for role in roles)

    async def dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise PermissionDeniedError()
        return current_user

    return dependency


def require_permission(
    permission: str,
    resource_id_param: str | None = None,
) -> PermissionDependency:
    async def dependency(
        current_user: Annotated[User, Depends(get_current_user)],
        role_permission_service: Any = ROLE_PERMISSION_SERVICE_DEPENDENCY,
    ) -> User:
        _ = resource_id_param
        has_permission = (
            await role_permission_service.has_permission(current_user.role, permission)
            if hasattr(role_permission_service, "has_permission")
            else user_has_permission(current_user, permission)
        )
        if not has_permission:
            raise PermissionDeniedError()
        return current_user

    return dependency
