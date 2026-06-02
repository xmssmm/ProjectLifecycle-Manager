from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BusinessException,
    PermissionDeniedError,
    ResourceNotFoundError,
    SelfReviewDeniedError,
)
from app.models.main_projects import (
    MainProject,
    MainProjectStatus,
    ProjectReview,
    ProjectReviewDecision,
)
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.schemas.main_projects import (
    MainProjectCreate,
    MainProjectReviewRequest,
    MainProjectReviewUpdate,
    MainProjectUpdate,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter, to_audit_state
from app.services.notifications import NotificationService

VIEW_ALL_PROJECT_ROLES = frozenset(
    {
        UserRole.admin,
        UserRole.dept_manager,
        UserRole.finance_manager,
        UserRole.proj_leader,
        UserRole.proj_member,
    },
)
PHASE_DEFINITIONS = (
    (1, "initiation", "立项"),
    (2, "procurement", "采购"),
    (3, "contract", "合同"),
    (4, "acceptance", "验收"),
    (5, "payment", "付款"),
    (6, "post_review", "后评价"),
)


@dataclass(frozen=True)
class ProjectProgressFunnelSubProject:
    id: UUID
    project_no: str
    name: str
    status: SubProjectStatus
    phase_status: PhaseStatus


@dataclass(frozen=True)
class ProjectProgressFunnelItem:
    phase_no: int
    code: str
    name: str
    sub_project_count: int
    sub_projects: list[ProjectProgressFunnelSubProject]


@dataclass(frozen=True)
class ProjectProgressFunnel:
    main_project_id: UUID
    total_sub_projects: int
    items: list[ProjectProgressFunnelItem]


class MainProjectRepository(Protocol):
    async def list_projects(self, *, page: int, page_size: int) -> tuple[list[MainProject], int]:
        ...

    async def get_by_id(self, project_id: UUID) -> MainProject | None:
        ...

    async def next_project_sequence(self) -> int:
        ...

    async def count_open_sub_projects(self, main_project_id: UUID) -> int:
        ...

    async def list_sub_projects_by_main_project(self, main_project_id: UUID) -> list[SubProject]:
        ...

    async def list_phases_by_sub_project_ids(self, sub_project_ids: Sequence[UUID]) -> list[Phase]:
        ...

    async def list_active_user_ids_by_role(
        self,
        role: UserRole,
        *,
        excluding_user_id: UUID | None = None,
    ) -> list[UUID]:
        ...

    def add(self, project: MainProject) -> None:
        ...

    def add_review(self, review: ProjectReview) -> None:
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
            .options(
                selectinload(MainProject.department),
                selectinload(MainProject.creator),
            )
            .order_by(MainProject.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        projects = list((await self._session.scalars(statement)).all())
        return projects, int(total or 0)

    async def get_by_id(self, project_id: UUID) -> MainProject | None:
        project = await self._session.scalar(
            select(MainProject)
            .options(
                selectinload(MainProject.department),
                selectinload(MainProject.creator),
            )
            .where(MainProject.id == project_id),
        )
        return project if isinstance(project, MainProject) else None

    async def next_project_sequence(self) -> int:
        value = await self._session.scalar(text("SELECT nextval('main_project_no_seq')"))
        return int(cast(int, value))

    async def count_open_sub_projects(self, main_project_id: UUID) -> int:
        value = await self._session.scalar(
            select(func.count()).select_from(SubProject).where(
                SubProject.main_project_id == main_project_id,
                SubProject.status.notin_([SubProjectStatus.closed, SubProjectStatus.terminated]),
                SubProject.status != SubProjectStatus.completed,
            ),
        )
        return int(value or 0)

    async def list_sub_projects_by_main_project(self, main_project_id: UUID) -> list[SubProject]:
        result = await self._session.scalars(
            select(SubProject)
            .options(
                selectinload(SubProject.department),
                selectinload(SubProject.main_project),
                selectinload(SubProject.manager),
            )
            .where(SubProject.main_project_id == main_project_id)
            .order_by(SubProject.project_no),
        )
        return list(result.all())

    async def list_phases_by_sub_project_ids(self, sub_project_ids: Sequence[UUID]) -> list[Phase]:
        if not sub_project_ids:
            return []
        result = await self._session.scalars(
            select(Phase)
            .where(Phase.sub_project_id.in_(sub_project_ids))
            .order_by(Phase.phase_no),
        )
        return list(result.all())

    async def list_active_user_ids_by_role(
        self,
        role: UserRole,
        *,
        excluding_user_id: UUID | None = None,
    ) -> list[UUID]:
        conditions = [User.role == role, User.status == UserStatus.active]
        if excluding_user_id is not None:
            conditions.append(User.id != excluding_user_id)
        result = await self._session.scalars(select(User.id).where(*conditions))
        return list(result.all())

    def add(self, project: MainProject) -> None:
        self._session.add(project)

    def add_review(self, review: ProjectReview) -> None:
        self._session.add(review)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, project: MainProject) -> None:
        await self._session.refresh(project)


class InMemoryMainProjectRepository:
    def __init__(
        self,
        projects: Sequence[MainProject] | None = None,
        *,
        sub_projects: Sequence[SubProject] | None = None,
        phases: Sequence[Phase] | None = None,
        users: Sequence[User] | None = None,
        next_sequence: int = 1,
    ) -> None:
        self.projects = list(projects or [])
        self.sub_projects = list(sub_projects or [])
        self.phases = list(phases or [])
        self.users = list(users or [])
        self.reviews: list[ProjectReview] = []
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

    async def count_open_sub_projects(self, main_project_id: UUID) -> int:
        return sum(
            1
            for sub_project in self.sub_projects
            if sub_project.main_project_id == main_project_id
            and sub_project.status
            not in {
                SubProjectStatus.completed,
                SubProjectStatus.closed,
                SubProjectStatus.terminated,
            }
        )

    async def list_sub_projects_by_main_project(self, main_project_id: UUID) -> list[SubProject]:
        return sorted(
            [
                sub_project
                for sub_project in self.sub_projects
                if sub_project.main_project_id == main_project_id
            ],
            key=lambda sub_project: sub_project.project_no,
        )

    async def list_phases_by_sub_project_ids(self, sub_project_ids: Sequence[UUID]) -> list[Phase]:
        ids = set(sub_project_ids)
        return sorted(
            [phase for phase in self.phases if phase.sub_project_id in ids],
            key=lambda phase: (str(phase.sub_project_id), phase.phase_no),
        )

    async def list_active_user_ids_by_role(
        self,
        role: UserRole,
        *,
        excluding_user_id: UUID | None = None,
    ) -> list[UUID]:
        return [
            user.id
            for user in self.users
            if user.role == role
            and user.status == UserStatus.active
            and user.id != excluding_user_id
        ]

    def add(self, project: MainProject) -> None:
        self.projects.append(project)

    def add_review(self, review: ProjectReview) -> None:
        self.reviews.append(review)

    async def commit(self) -> None:
        return None

    async def refresh(self, project: MainProject) -> None:
        return None


class MainProjectService:
    def __init__(
        self,
        *,
        repository: MainProjectRepository,
        notification_service: NotificationService | None = None,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._notification_service = notification_service
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

    async def get_progress_funnel(
        self,
        *,
        actor: User,
        project_id: UUID,
    ) -> ProjectProgressFunnel:
        self._ensure_view_all(actor)
        await self._get_existing_project(project_id)
        sub_projects = await self._repository.list_sub_projects_by_main_project(project_id)
        phases = await self._repository.list_phases_by_sub_project_ids(
            [sub_project.id for sub_project in sub_projects],
        )
        phases_by_sub_project = self._index_phases_by_sub_project(phases)
        return ProjectProgressFunnel(
            main_project_id=project_id,
            total_sub_projects=len(sub_projects),
            items=[
                self._build_progress_funnel_item(
                    phase_no=phase_no,
                    code=code,
                    name=name,
                    sub_projects=sub_projects,
                    phases_by_sub_project=phases_by_sub_project,
                )
                for phase_no, code, name in PHASE_DEFINITIONS
            ],
        )

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

    async def submit_project(
        self,
        *,
        actor: User,
        project_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> MainProject:
        project = await self._get_existing_project(project_id)
        if project.creator_id != actor.id:
            raise PermissionDeniedError()
        if project.status not in {MainProjectStatus.pending_review, MainProjectStatus.rejected}:
            raise self._invalid_status(project.status, "当前状态不允许提交主项目")

        before_state = to_audit_state(project)
        project.status = MainProjectStatus.pending_review
        await self._repository.commit()
        await self._repository.refresh(project)

        receivers = await self._repository.list_active_user_ids_by_role(
            UserRole.dept_manager,
            excluding_user_id=actor.id,
        )
        await self._send_notification(
            scenario="project_pending_review",
            receivers=receivers,
            source_id=project.id,
            payload={
                "project_no": project.project_no,
                "project_name": project.name,
            },
        )
        self._record_audit(
            action="main_project.submit",
            actor=actor,
            project=project,
            before_state=before_state,
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={},
        )
        return project

    async def review_project(
        self,
        *,
        actor: User,
        project_id: UUID,
        payload: MainProjectReviewRequest,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> MainProject:
        if actor.role not in {UserRole.admin, UserRole.dept_manager}:
            raise PermissionDeniedError()

        project = await self._get_existing_project(project_id)
        if project.creator_id == actor.id and actor.role != UserRole.admin:
            peer_reviewers = await self._repository.list_active_user_ids_by_role(
                UserRole.dept_manager,
                excluding_user_id=actor.id,
            )
            if peer_reviewers:
                raise SelfReviewDeniedError()
        if project.status != MainProjectStatus.pending_review:
            raise self._invalid_status(project.status, "当前状态不允许审核主项目")

        before_state = to_audit_state(project)
        modified_fields = self._apply_review_updates(project, payload.updates)
        from_status = project.status
        project.status = (
            MainProjectStatus.not_started
            if payload.decision == ProjectReviewDecision.approve
            else MainProjectStatus.rejected
        )
        now = datetime.now(UTC)
        review = ProjectReview(
            id=uuid4(),
            main_project_id=project.id,
            reviewer_id=actor.id,
            decision=payload.decision,
            from_status=from_status,
            to_status=project.status,
            review_comment=payload.review_comment,
            modified_fields=modified_fields,
            admin_override=actor.role == UserRole.admin,
            reviewed_at=now,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_review(review)
        await self._repository.commit()
        await self._repository.refresh(project)

        if project.creator_id is not None:
            await self._send_notification(
                scenario="project_review_result",
                receivers=[project.creator_id],
                source_id=project.id,
                payload={
                    "project_no": project.project_no,
                    "project_name": project.name,
                    "decision": payload.decision.value,
                    "review_comment": payload.review_comment,
                },
            )
        self._record_audit(
            action="main_project.review",
            actor=actor,
            project=project,
            before_state=before_state,
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={
                "admin_override": actor.role == UserRole.admin,
                "decision": payload.decision.value,
                "modified_fields": modified_fields,
            },
        )
        return project

    async def close_project(self, *, actor: User, project_id: UUID) -> MainProject:
        if actor.role != UserRole.dept_manager:
            raise PermissionDeniedError()

        project = await self._get_existing_project(project_id)
        if project.status == MainProjectStatus.closed:
            if project.closed_at is None:
                project.closed_at = datetime.now(UTC)
                await self._repository.commit()
                await self._repository.refresh(project)
            return project
        if project.status not in {MainProjectStatus.not_started, MainProjectStatus.in_progress}:
            raise self._invalid_status(project.status, "当前状态不允许结项主项目")

        open_sub_project_count = await self._repository.count_open_sub_projects(project.id)
        if open_sub_project_count > 0:
            raise BusinessException(
                code=3003,
                message="仍存在未结项或未中止的子项目",
                status_code=409,
                data={"open_sub_project_count": open_sub_project_count},
            )

        now = datetime.now(UTC)
        project.status = MainProjectStatus.closed
        project.closed_at = now
        project.updated_at = now
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

    @staticmethod
    def _index_phases_by_sub_project(phases: Sequence[Phase]) -> dict[UUID, dict[int, Phase]]:
        indexed: dict[UUID, dict[int, Phase]] = {}
        for phase in phases:
            indexed.setdefault(phase.sub_project_id, {})[phase.phase_no] = phase
        return indexed

    @staticmethod
    def _build_progress_funnel_item(
        *,
        phase_no: int,
        code: str,
        name: str,
        sub_projects: Sequence[SubProject],
        phases_by_sub_project: dict[UUID, dict[int, Phase]],
    ) -> ProjectProgressFunnelItem:
        drill_items: list[ProjectProgressFunnelSubProject] = []
        for sub_project in sub_projects:
            phase = phases_by_sub_project.get(sub_project.id, {}).get(phase_no)
            if phase is None or phase.status != PhaseStatus.in_progress:
                continue
            drill_items.append(
                ProjectProgressFunnelSubProject(
                    id=sub_project.id,
                    project_no=sub_project.project_no,
                    name=sub_project.name,
                    status=sub_project.status,
                    phase_status=phase.status,
                ),
            )
        return ProjectProgressFunnelItem(
            phase_no=phase_no,
            code=code,
            name=name,
            sub_project_count=len(drill_items),
            sub_projects=drill_items,
        )

    async def _send_notification(
        self,
        *,
        scenario: str,
        receivers: Sequence[UUID],
        source_id: UUID,
        payload: dict[str, object],
    ) -> None:
        if self._notification_service is None or not receivers:
            return
        await self._notification_service.send(
            scenario=scenario,
            receivers=receivers,
            source_id=source_id,
            payload=payload,
        )

    @staticmethod
    def _apply_review_updates(
        project: MainProject,
        updates: MainProjectReviewUpdate | None,
    ) -> dict[str, dict[str, object | None]]:
        if updates is None:
            return {}

        modified_fields: dict[str, dict[str, object | None]] = {}
        fields = updates.model_fields_set
        update_values = {
            "name": updates.name,
            "dept_id": updates.dept_id,
            "total_budget": updates.total_budget,
            "expected_finish_date": updates.expected_finish_date,
            "remark": updates.remark,
        }
        for field_name, new_value in update_values.items():
            if field_name not in fields:
                continue
            old_value = getattr(project, field_name)
            if old_value == new_value:
                continue
            modified_fields[field_name] = {
                "before": MainProjectService._audit_json_value(old_value),
                "after": MainProjectService._audit_json_value(new_value),
            }
            setattr(project, field_name, new_value)
        return modified_fields

    @staticmethod
    def _record_audit(
        *,
        action: str,
        actor: User,
        project: MainProject,
        before_state: dict[str, object],
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
        extra: dict[str, object],
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id or actor.id,
                action=action,
                target_type="main_project",
                target_id=str(project.id),
                before_state=before_state,
                after_state=to_audit_state(project),
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra=extra,
                request_id=context.request_id,
            ),
        )

    @staticmethod
    def _audit_json_value(value: object | None) -> object | None:
        if isinstance(value, UUID | Decimal | date):
            return str(value)
        return value

    @staticmethod
    def _invalid_status(status: MainProjectStatus, message: str) -> BusinessException:
        return BusinessException(
            code=3003,
            message=message,
            status_code=409,
            data={"status": status.value},
        )
