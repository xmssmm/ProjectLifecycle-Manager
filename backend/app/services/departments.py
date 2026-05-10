from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DepartmentHasActiveUsersError,
    PermissionDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.models.departments import Department
from app.models.users import User, UserRole, UserStatus
from app.schemas.departments import DepartmentCreate, DepartmentUpdate


class DepartmentRepository(Protocol):
    async def list_departments(self) -> list[Department]:
        ...

    async def get_by_id(self, department_id: UUID) -> Department | None:
        ...

    async def get_by_code(self, code: str) -> Department | None:
        ...

    async def get_by_name(self, name: str) -> Department | None:
        ...

    async def count_active_users(self, department_id: UUID) -> int:
        ...

    def add(self, department: Department) -> None:
        ...

    async def delete(self, department: Department) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh(self, department: Department) -> None:
        ...


class SqlAlchemyDepartmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_departments(self) -> list[Department]:
        result = await self._session.scalars(select(Department).order_by(Department.code.asc()))
        return list(result.all())

    async def get_by_id(self, department_id: UUID) -> Department | None:
        department = await self._session.get(Department, department_id)
        return department if isinstance(department, Department) else None

    async def get_by_code(self, code: str) -> Department | None:
        return cast(
            Department | None,
            await self._session.scalar(select(Department).where(Department.code == code)),
        )

    async def get_by_name(self, name: str) -> Department | None:
        return cast(
            Department | None,
            await self._session.scalar(select(Department).where(Department.name == name)),
        )

    async def count_active_users(self, department_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(User).where(
                User.dept_id == department_id,
                User.status != UserStatus.disabled,
            ),
        )
        return int(count or 0)

    def add(self, department: Department) -> None:
        self._session.add(department)

    async def delete(self, department: Department) -> None:
        await self._session.delete(department)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, department: Department) -> None:
        await self._session.refresh(department)


class InMemoryDepartmentRepository:
    def __init__(
        self,
        departments: Sequence[Department] | None = None,
        *,
        active_user_counts: dict[UUID, int] | None = None,
    ) -> None:
        self.departments = list(departments or [])
        self._active_user_counts = active_user_counts or {}

    async def list_departments(self) -> list[Department]:
        return sorted(self.departments, key=lambda department: department.code)

    async def get_by_id(self, department_id: UUID) -> Department | None:
        return next(
            (department for department in self.departments if department.id == department_id),
            None,
        )

    async def get_by_code(self, code: str) -> Department | None:
        return next(
            (department for department in self.departments if department.code == code),
            None,
        )

    async def get_by_name(self, name: str) -> Department | None:
        return next(
            (department for department in self.departments if department.name == name),
            None,
        )

    async def count_active_users(self, department_id: UUID) -> int:
        return self._active_user_counts.get(department_id, 0)

    def add(self, department: Department) -> None:
        self.departments.append(department)

    async def delete(self, department: Department) -> None:
        self.departments.remove(department)

    async def commit(self) -> None:
        return None

    async def refresh(self, department: Department) -> None:
        return None


class DepartmentService:
    def __init__(self, *, repository: DepartmentRepository) -> None:
        self._repository = repository

    async def list_departments(self) -> list[Department]:
        return await self._repository.list_departments()

    async def create_department(
        self,
        *,
        actor: User,
        payload: DepartmentCreate,
    ) -> Department:
        self._ensure_admin(actor)
        await self._ensure_unique_code(payload.code)
        await self._ensure_unique_name(payload.name)

        now = datetime.now(UTC)
        department = Department(
            code=payload.code,
            name=payload.name,
            created_at=now,
            updated_at=now,
        )
        self._repository.add(department)
        await self._repository.commit()
        await self._repository.refresh(department)
        return department

    async def update_department(
        self,
        *,
        actor: User,
        department_id: UUID,
        payload: DepartmentUpdate,
    ) -> Department:
        self._ensure_admin(actor)
        department = await self._get_existing_department(department_id)
        if payload.code is not None and payload.code != department.code:
            await self._ensure_unique_code(payload.code, excluding_department_id=department.id)
            department.code = payload.code
        if payload.name is not None and payload.name != department.name:
            await self._ensure_unique_name(payload.name, excluding_department_id=department.id)
            department.name = payload.name

        await self._repository.commit()
        await self._repository.refresh(department)
        return department

    async def delete_department(self, *, actor: User, department_id: UUID) -> Department:
        self._ensure_admin(actor)
        department = await self._get_existing_department(department_id)
        active_user_count = await self._repository.count_active_users(department.id)
        if active_user_count > 0:
            raise DepartmentHasActiveUsersError(active_user_count)

        await self._repository.delete(department)
        await self._repository.commit()
        return department

    async def _get_existing_department(self, department_id: UUID) -> Department:
        department = await self._repository.get_by_id(department_id)
        if department is None:
            raise ResourceNotFoundError("部门不存在")
        return department

    async def _ensure_unique_code(
        self,
        code: str,
        *,
        excluding_department_id: UUID | None = None,
    ) -> None:
        existing = await self._repository.get_by_code(code)
        if existing is not None and existing.id != excluding_department_id:
            raise ResourceConflictError("部门编码已存在", data={"field": "code"})

    async def _ensure_unique_name(
        self,
        name: str,
        *,
        excluding_department_id: UUID | None = None,
    ) -> None:
        existing = await self._repository.get_by_name(name)
        if existing is not None and existing.id != excluding_department_id:
            raise ResourceConflictError("部门名称已存在", data={"field": "name"})

    @staticmethod
    def _ensure_admin(actor: User) -> None:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()
