from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, PermissionDeniedError, ResourceNotFoundError
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.users import User, UserRole
from app.schemas.main_projects import MainProjectCreate, MainProjectUpdate

VIEW_ALL_PROJECT_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)


class MainProjectRepository(Protocol):
    async def list_projects(self, *, page: int, page_size: int) -> tuple[list[MainProject], int]:
        ...

    async def get_by_id(self, project_id: UUID) -> MainProject | None:
        ...

    async def next_project_sequence(self) -> int:
        ...

    def add(self, project: MainProject) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh(self, project: MainProject) -> None:
        ...


class SqlAlchemyMainProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_projects(self, *, page: int, page_size: int) -> tuple[list[MainProject], int]:
        total = await self._session.scalar(select(func.count()).select_from(MainProject))
        statement = (
            select(MainProject)
            .order_by(MainProject.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        projects = list((await self._session.scalars(statement)).all())
        return projects, int(total or 0)

    async def get_by_id(self, project_id: UUID) -> MainProject | None:
        project = await self._session.get(MainProject, project_id)
        return project if isinstance(project, MainProject) else None

    async def next_project_sequence(self) -> int:
        value = await self._session.scalar(text("SELECT nextval('main_project_no_seq')"))
        return int(cast(int, value))

    def add(self, project: MainProject) -> None:
        self._session.add(project)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, project: MainProject) -> None:
        await self._session.refresh(project)


class InMemoryMainProjectRepository:
    def __init__(
        self,
        projects: Sequence[MainProject] | None = None,
        *,
        next_sequence: int = 1,
    ) -> None:
        self.projects = list(projects or [])
        self._next_sequence = next_sequence

    async def list_projects(self, *, page: int, page_size: int) -> tuple[list[MainProject], int]:
        ordered = sorted(self.projects, key=lambda project: project.created_at, reverse=True)
        start = (page - 1) * page_size
        return ordered[start : start + page_size], len(ordered)

    async def get_by_id(self, project_id: UUID) -> MainProject | None:
        return next((project for project in self.projects if project.id == project_id), None)

    async def next_project_sequence(self) -> int:
        value = self._next_sequence
        self._next_sequence += 1
        return value

    def add(self, project: MainProject) -> None:
        self.projects.append(project)

    async def commit(self) -> None:
        return None

    async def refresh(self, project: MainProject) -> None:
        return None


class MainProjectService:
    def __init__(
        self,
        *,
        repository: MainProjectRepository,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._today_provider = today_provider

    async def list_projects(
        self,
        *,
        actor: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MainProject], int]:
        self._ensure_view_all(actor)
        return await self._repository.list_projects(page=page, page_size=page_size)

    async def get_project(self, *, actor: User, project_id: UUID) -> MainProject:
        self._ensure_view_all(actor)
        return await self._get_existing_project(project_id)

    async def create_project(self, *, actor: User, payload: MainProjectCreate) -> MainProject:
        if actor.role != UserRole.dept_manager:
            raise PermissionDeniedError()

        now = datetime.now(UTC)
        sequence_value = await self._repository.next_project_sequence()
        project = MainProject(
            id=uuid4(),
            project_no=self._format_project_no(sequence_value),
            name=payload.name,
            dept_id=payload.dept_id,
            status=MainProjectStatus.pending_review,
            total_budget=payload.total_budget,
            expected_finish_date=payload.expected_finish_date,
            spent_amount=Decimal("0.00"),
            remark=payload.remark,
            creator_id=actor.id,
            created_at=now,
            updated_at=now,
        )
        self._repository.add(project)
        await self._repository.commit()
        await self._repository.refresh(project)
        return project

    async def update_project(
        self,
        *,
        actor: User,
        project_id: UUID,
        payload: MainProjectUpdate,
    ) -> MainProject:
        project = await self._get_existing_project(project_id)
        if project.creator_id != actor.id:
            raise PermissionDeniedError()
        if project.status != MainProjectStatus.rejected:
            raise BusinessException(
                code=3003,
                message="当前状态不允许编辑主项目",
                status_code=409,
                data={"status": project.status.value},
            )

        fields = payload.model_fields_set
        if payload.name is not None:
            project.name = payload.name
        if payload.dept_id is not None:
            project.dept_id = payload.dept_id
        if payload.total_budget is not None:
            project.total_budget = payload.total_budget
        if payload.expected_finish_date is not None:
            project.expected_finish_date = payload.expected_finish_date
        if "remark" in fields:
            project.remark = payload.remark

        await self._repository.commit()
        await self._repository.refresh(project)
        return project

    async def _get_existing_project(self, project_id: UUID) -> MainProject:
        project = await self._repository.get_by_id(project_id)
        if project is None:
            raise ResourceNotFoundError("主项目不存在")
        return project

    def _format_project_no(self, sequence_value: int) -> str:
        return f"Z-{self._today_provider().year}-{sequence_value:04d}"

    @staticmethod
    def _ensure_view_all(actor: User) -> None:
        if actor.role not in VIEW_ALL_PROJECT_ROLES:
            raise PermissionDeniedError()
