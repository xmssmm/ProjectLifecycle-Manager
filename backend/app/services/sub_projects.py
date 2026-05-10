from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, PermissionDeniedError, ResourceNotFoundError
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole
from app.schemas.sub_projects import SubProjectCreate, SubProjectUpdate

VIEW_ALL_SUB_PROJECT_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)
OPEN_MAIN_PROJECT_STATUSES = frozenset(
    {MainProjectStatus.not_started, MainProjectStatus.in_progress},
)


class SubProjectRepository(Protocol):
    async def list_sub_projects(
        self,
        *,
        actor: User,
        page: int,
        page_size: int,
    ) -> tuple[list[SubProject], int]:
        ...

    async def get_by_id(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_main_project(self, main_project_id: UUID) -> MainProject | None:
        ...

    async def next_sub_project_sequence(self, main_project_id: UUID) -> int:
        ...

    def add(self, sub_project: SubProject) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh(self, sub_project: SubProject) -> None:
        ...


class SqlAlchemySubProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_sub_projects(
        self,
        *,
        actor: User,
        page: int,
        page_size: int,
    ) -> tuple[list[SubProject], int]:
        conditions = []
        if actor.role not in VIEW_ALL_SUB_PROJECT_ROLES:
            conditions.append(SubProject.manager_id == actor.id)

        total = await self._session.scalar(
            select(func.count()).select_from(SubProject).where(*conditions),
        )
        statement = (
            select(SubProject)
            .where(*conditions)
            .order_by(SubProject.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        sub_projects = list((await self._session.scalars(statement)).all())
        return sub_projects, int(total or 0)

    async def get_by_id(self, sub_project_id: UUID) -> SubProject | None:
        sub_project = await self._session.get(SubProject, sub_project_id)
        return sub_project if isinstance(sub_project, SubProject) else None

    async def get_main_project(self, main_project_id: UUID) -> MainProject | None:
        main_project = await self._session.get(MainProject, main_project_id)
        return main_project if isinstance(main_project, MainProject) else None

    async def next_sub_project_sequence(self, main_project_id: UUID) -> int:
        value = await self._session.scalar(
            text(
                """
                INSERT INTO sub_project_no_counters (main_project_id, next_sequence)
                VALUES (:main_project_id, 2)
                ON CONFLICT (main_project_id)
                DO UPDATE SET next_sequence = sub_project_no_counters.next_sequence + 1
                RETURNING next_sequence - 1
                """,
            ),
            {"main_project_id": main_project_id},
        )
        return int(value or 1)

    def add(self, sub_project: SubProject) -> None:
        self._session.add(sub_project)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, sub_project: SubProject) -> None:
        await self._session.refresh(sub_project)


class InMemorySubProjectRepository:
    def __init__(
        self,
        *,
        main_projects: Sequence[MainProject],
        sub_projects: Sequence[SubProject] | None = None,
        next_sequences: dict[UUID, int] | None = None,
    ) -> None:
        self.main_projects = list(main_projects)
        self.sub_projects = list(sub_projects or [])
        self.next_sequences = dict(next_sequences or {})

    async def list_sub_projects(
        self,
        *,
        actor: User,
        page: int,
        page_size: int,
    ) -> tuple[list[SubProject], int]:
        if actor.role in VIEW_ALL_SUB_PROJECT_ROLES:
            filtered = list(self.sub_projects)
        else:
            filtered = [
                sub_project
                for sub_project in self.sub_projects
                if sub_project.manager_id == actor.id
            ]
        ordered = sorted(filtered, key=lambda sub_project: sub_project.created_at, reverse=True)
        start = (page - 1) * page_size
        return ordered[start : start + page_size], len(ordered)

    async def get_by_id(self, sub_project_id: UUID) -> SubProject | None:
        return next(
            (sub_project for sub_project in self.sub_projects if sub_project.id == sub_project_id),
            None,
        )

    async def get_main_project(self, main_project_id: UUID) -> MainProject | None:
        return next(
            (project for project in self.main_projects if project.id == main_project_id),
            None,
        )

    async def next_sub_project_sequence(self, main_project_id: UUID) -> int:
        sequence = self.next_sequences.get(main_project_id, 1)
        self.next_sequences[main_project_id] = sequence + 1
        return sequence

    def add(self, sub_project: SubProject) -> None:
        self.sub_projects.append(sub_project)

    async def commit(self) -> None:
        return None

    async def refresh(self, sub_project: SubProject) -> None:
        return None


class SubProjectService:
    def __init__(self, *, repository: SubProjectRepository) -> None:
        self._repository = repository

    async def list_sub_projects(
        self,
        *,
        actor: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SubProject], int]:
        return await self._repository.list_sub_projects(
            actor=actor,
            page=page,
            page_size=page_size,
        )

    async def get_sub_project(self, *, actor: User, sub_project_id: UUID) -> SubProject:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        self._ensure_visible(actor, sub_project)
        return sub_project

    async def create_sub_project(self, *, actor: User, payload: SubProjectCreate) -> SubProject:
        if actor.role != UserRole.proj_leader:
            raise PermissionDeniedError()
        main_project = await self._get_existing_main_project(payload.main_project_id)
        if main_project.status not in OPEN_MAIN_PROJECT_STATUSES:
            raise self._invalid_status(main_project.status.value, "当前主项目状态不允许创建子项目")

        sequence = await self._repository.next_sub_project_sequence(main_project.id)
        now = datetime.now(UTC)
        sub_project = SubProject(
            id=uuid4(),
            project_no=f"{main_project.project_no}-ZX-{sequence:03d}",
            name=payload.name,
            main_project_id=main_project.id,
            dept_id=payload.dept_id,
            budget=payload.budget,
            manager_id=actor.id,
            creator_id=actor.id,
            status=SubProjectStatus.pending_review,
            plan_end_date=payload.plan_end_date,
            actual_end_date=None,
            spent_amount=Decimal("0.00"),
            remark=payload.remark,
            created_at=now,
            updated_at=now,
        )
        self._repository.add(sub_project)
        await self._repository.commit()
        await self._repository.refresh(sub_project)
        return sub_project

    async def update_sub_project(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        payload: SubProjectUpdate,
    ) -> SubProject:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        if sub_project.creator_id != actor.id:
            raise PermissionDeniedError()
        if sub_project.status != SubProjectStatus.rejected:
            raise self._invalid_status(sub_project.status.value, "当前状态不允许编辑子项目")

        fields = payload.model_fields_set
        if payload.name is not None:
            sub_project.name = payload.name
        if payload.dept_id is not None:
            sub_project.dept_id = payload.dept_id
        if payload.budget is not None:
            sub_project.budget = payload.budget
        if "plan_end_date" in fields:
            sub_project.plan_end_date = payload.plan_end_date
        if "remark" in fields:
            sub_project.remark = payload.remark

        await self._repository.commit()
        await self._repository.refresh(sub_project)
        return sub_project

    async def _get_existing_sub_project(self, sub_project_id: UUID) -> SubProject:
        sub_project = await self._repository.get_by_id(sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("子项目不存在")
        return sub_project

    async def _get_existing_main_project(self, main_project_id: UUID) -> MainProject:
        main_project = await self._repository.get_main_project(main_project_id)
        if main_project is None:
            raise ResourceNotFoundError("主项目不存在")
        return main_project

    @staticmethod
    def _ensure_visible(actor: User, sub_project: SubProject) -> None:
        if actor.role in VIEW_ALL_SUB_PROJECT_ROLES or sub_project.manager_id == actor.id:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _invalid_status(status: str, message: str) -> BusinessException:
        return BusinessException(
            code=3003,
            message=message,
            status_code=409,
            data={"status": status},
        )
