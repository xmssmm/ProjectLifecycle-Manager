from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User, UserRole, UserStatus


class SystemHealthWarning(TypedDict):
    code: str
    message: str
    data: dict[str, int]


class RoleHealthReader(Protocol):
    async def count_active_users_by_role(self, role: UserRole) -> int:
        ...


class SqlAlchemyRoleHealthReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_active_users_by_role(self, role: UserRole) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(User).where(
                User.role == role,
                User.status != UserStatus.disabled,
            ),
        )
        return int(count or 0)


class InMemoryRoleHealthReader:
    def __init__(
        self,
        *,
        dept_manager_count: int = 0,
        role_counts: Mapping[UserRole, int] | None = None,
    ) -> None:
        counts = dict(role_counts or {})
        counts[UserRole.dept_manager] = dept_manager_count
        self._role_counts = counts

    async def count_active_users_by_role(self, role: UserRole) -> int:
        return self._role_counts.get(role, 0)


class SystemHealthService:
    def __init__(
        self,
        *,
        role_reader: RoleHealthReader,
        required_dept_manager_count: int = 2,
    ) -> None:
        self._role_reader = role_reader
        self._required_dept_manager_count = required_dept_manager_count

    async def collect_warnings(self) -> list[SystemHealthWarning]:
        warnings: list[SystemHealthWarning] = []
        dept_manager_count = await self._role_reader.count_active_users_by_role(
            UserRole.dept_manager,
        )
        if dept_manager_count < self._required_dept_manager_count:
            message = f"生产环境至少需要 {self._required_dept_manager_count} 名综合部负责人"
            warnings.append(
                {
                    "code": "dept_manager_minimum_not_met",
                    "message": message,
                    "data": {
                        "current_count": dept_manager_count,
                        "required_count": self._required_dept_manager_count,
                    },
                },
            )
        return warnings
