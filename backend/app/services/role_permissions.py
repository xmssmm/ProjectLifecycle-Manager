from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ValidationFailedError
from app.core.permissions import DEFAULT_PERMISSION_MATRIX
from app.models.role_permissions import RolePermission
from app.models.users import User, UserRole
from app.schemas.role_permissions import (
    RolePermissionMatrixRead,
    RolePermissionOptionRead,
    RolePermissionRead,
)

ROLE_ORDER = (
    UserRole.admin,
    UserRole.dept_manager,
    UserRole.finance_manager,
    UserRole.proj_leader,
    UserRole.proj_member,
)

PERMISSION_LABELS: dict[str, str] = {
    "user.manage": "用户管理",
    "system.config": "系统配置",
    "audit_log.read": "审计日志查看",
    "database.export": "数据导出",
    "role_permission.manage": "角色权限管理",
    "main_project.create": "主项目创建",
    "main_project.edit": "主项目编辑",
    "main_project.review": "主项目审核",
    "main_project.close": "主项目结项",
    "project.import": "项目导入",
    "sub_project.create": "子项目创建",
    "sub_project.review": "子项目审核",
    "sub_project.terminate": "子项目终止",
    "phase.promote": "环节流转",
    "acceptance_step.create": "验收步骤创建",
    "acceptance_step.complete": "验收步骤完成",
    "payment.create": "付款创建",
    "payment.reverse": "付款冲销",
    "document.upload": "文件上传",
    "document.download": "文件下载",
    "task.assign": "任务指派",
    "task.complete": "任务完成",
    "revoke_request.submit": "撤回申请提交",
    "revoke_request.review": "撤回申请审核",
    "report.generate": "报表生成",
    "project.view_all": "查看全部项目",
    "project.view_own": "查看本人项目",
}


class SqlAlchemyRolePermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_role_permissions(self, role: UserRole) -> list[RolePermission]:
        result = await self._session.scalars(
            select(RolePermission)
            .where(RolePermission.role == role)
            .order_by(RolePermission.permission_code.asc()),
        )
        return list(result.all())

    async def replace_role_permissions(
        self,
        *,
        role: UserRole,
        rows: Sequence[RolePermission],
    ) -> None:
        await self._session.execute(delete(RolePermission).where(RolePermission.role == role))
        for row in rows:
            self._session.add(row)
        await self._session.commit()


class InMemoryRolePermissionRepository:
    def __init__(self, permissions: Sequence[RolePermission] | None = None) -> None:
        self.permissions = list(permissions or [])

    async def list_role_permissions(self, role: UserRole) -> list[RolePermission]:
        return sorted(
            [permission for permission in self.permissions if permission.role == role],
            key=lambda permission: permission.permission_code,
        )

    async def replace_role_permissions(
        self,
        *,
        role: UserRole,
        rows: Sequence[RolePermission],
    ) -> None:
        self.permissions = [
            permission for permission in self.permissions if permission.role != role
        ]
        self.permissions.extend(rows)


class RolePermissionService:
    def __init__(
        self,
        *,
        repository: SqlAlchemyRolePermissionRepository | InMemoryRolePermissionRepository,
    ) -> None:
        self._repository = repository

    async def effective_permissions(self, role: UserRole) -> list[str]:
        rows = await self._repository.list_role_permissions(role)
        if not rows:
            return [
                permission
                for permission, allowed_roles in DEFAULT_PERMISSION_MATRIX.items()
                if role in allowed_roles
            ]
        return [
            permission
            for permission in DEFAULT_PERMISSION_MATRIX
            if any(row.permission_code == permission and row.enabled for row in rows)
        ]

    async def has_permission(self, role: UserRole, permission_code: str) -> bool:
        return permission_code in await self.effective_permissions(role)

    async def list_matrix(self, *, actor: User) -> RolePermissionMatrixRead:
        self._ensure_admin(actor)
        return RolePermissionMatrixRead(
            permissions=[
                RolePermissionOptionRead(code=code, label=PERMISSION_LABELS.get(code, code))
                for code in DEFAULT_PERMISSION_MATRIX
            ],
            items=[
                RolePermissionRead(
                    role=role,
                    permission_codes=await self.effective_permissions(role),
                )
                for role in ROLE_ORDER
            ],
        )

    async def update_role_permissions(
        self,
        *,
        actor: User,
        role: UserRole,
        permission_codes: Sequence[str],
    ) -> RolePermissionRead:
        self._ensure_admin(actor)
        unknown_codes = sorted(set(permission_codes) - set(DEFAULT_PERMISSION_MATRIX))
        if unknown_codes:
            raise ValidationFailedError(
                "未知权限编码",
                data={"permission_codes": unknown_codes},
            )
        requested = list(dict.fromkeys(permission_codes))
        requested_set = set(requested)
        rows = [
            RolePermission(
                role=role,
                permission_code=code,
                enabled=code in requested_set,
            )
            for code in DEFAULT_PERMISSION_MATRIX
        ]
        await self._repository.replace_role_permissions(role=role, rows=rows)
        return RolePermissionRead(role=role, permission_codes=requested)

    @staticmethod
    def _ensure_admin(actor: User) -> None:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()
