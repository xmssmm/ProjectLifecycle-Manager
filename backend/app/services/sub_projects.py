from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessException,
    PermissionDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.models.main_projects import (
    MainProject,
    MainProjectStatus,
    ProjectReview,
    ProjectReviewDecision,
)
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import (
    SubProject,
    SubProjectHandover,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.users import User, UserRole, UserStatus
from app.schemas.sub_projects import (
    SubProjectBatchHandoverItem,
    SubProjectCreate,
    SubProjectHandoverRequest,
    SubProjectMemberCreate,
    SubProjectReviewRequest,
    SubProjectTerminateRequest,
    SubProjectUpdate,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter, to_audit_state
from app.services.notifications import NotificationService

VIEW_ALL_SUB_PROJECT_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)
OPEN_MAIN_PROJECT_STATUSES = frozenset(
    {MainProjectStatus.not_started, MainProjectStatus.in_progress},
)
APPROVED_SUB_PROJECT_STATUSES = frozenset(
    {
        SubProjectStatus.not_started,
        SubProjectStatus.in_progress,
        SubProjectStatus.completed,
        SubProjectStatus.closed,
    },
)
ACTIVE_HANDOVER_STATUSES = frozenset(
    {SubProjectStatus.not_started, SubProjectStatus.in_progress, SubProjectStatus.completed},
)
DEFAULT_PHASES = (
    (1, "initiation", "立项"),
    (2, "procurement", "采购"),
    (3, "contract", "合同"),
    (4, "acceptance", "验收"),
    (5, "payment", "付款"),
    (6, "post_review", "后评价"),
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

    async def get_user(self, user_id: UUID) -> User | None:
        ...

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        ...

    async def list_active_sub_projects_for_leader(self, user_id: UUID) -> list[SubProject]:
        ...

    async def list_sub_project_handovers(
        self,
        *,
        page: int,
        page_size: int,
        sub_project_id: UUID | None = None,
        from_user_id: UUID | None = None,
        to_user_id: UUID | None = None,
    ) -> tuple[list[SubProjectHandover], int]:
        ...

    async def get_member(
        self,
        *,
        sub_project_id: UUID,
        user_id: UUID,
    ) -> SubProjectMember | None:
        ...

    async def next_sub_project_sequence(self, main_project_id: UUID) -> int:
        ...

    async def sum_approved_budget(
        self,
        *,
        main_project_id: UUID,
        excluding_sub_project_id: UUID,
    ) -> Decimal:
        ...

    async def list_active_user_ids_by_role(
        self,
        role: UserRole,
        *,
        excluding_user_id: UUID | None = None,
    ) -> list[UUID]:
        ...

    async def phase_completion_counts(self, sub_project_id: UUID) -> tuple[int, int]:
        ...

    def add(self, sub_project: SubProject) -> None:
        ...

    def add_review(self, review: ProjectReview) -> None:
        ...

    def add_phase(self, phase: Phase) -> None:
        ...

    def add_member(self, member: SubProjectMember) -> None:
        ...

    def add_handover(self, handover: SubProjectHandover) -> None:
        ...

    async def delete_member(self, member: SubProjectMember) -> None:
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
            member_exists = (
                select(SubProjectMember.id)
                .where(
                    SubProjectMember.sub_project_id == SubProject.id,
                    SubProjectMember.user_id == actor.id,
                )
                .exists()
            )
            conditions.append(or_(SubProject.manager_id == actor.id, member_exists))

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

    async def get_user(self, user_id: UUID) -> User | None:
        user = await self._session.get(User, user_id)
        return user if isinstance(user, User) else None

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        result = await self._session.scalars(
            select(SubProjectMember)
            .where(SubProjectMember.sub_project_id == sub_project_id)
            .order_by(SubProjectMember.role_in_project.asc(), SubProjectMember.joined_at.asc()),
        )
        return list(result.all())

    async def list_active_sub_projects_for_leader(self, user_id: UUID) -> list[SubProject]:
        result = await self._session.scalars(
            select(SubProject)
            .where(
                SubProject.manager_id == user_id,
                SubProject.status.in_(list(ACTIVE_HANDOVER_STATUSES)),
            )
            .order_by(SubProject.created_at.desc()),
        )
        return list(result.all())

    async def list_sub_project_handovers(
        self,
        *,
        page: int,
        page_size: int,
        sub_project_id: UUID | None = None,
        from_user_id: UUID | None = None,
        to_user_id: UUID | None = None,
    ) -> tuple[list[SubProjectHandover], int]:
        conditions = []
        if sub_project_id is not None:
            conditions.append(SubProjectHandover.sub_project_id == sub_project_id)
        if from_user_id is not None:
            conditions.append(SubProjectHandover.from_user_id == from_user_id)
        if to_user_id is not None:
            conditions.append(SubProjectHandover.to_user_id == to_user_id)

        total = await self._session.scalar(
            select(func.count()).select_from(SubProjectHandover).where(*conditions),
        )
        result = await self._session.scalars(
            select(SubProjectHandover)
            .where(*conditions)
            .order_by(SubProjectHandover.operated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
        return list(result.all()), int(total or 0)

    async def get_member(
        self,
        *,
        sub_project_id: UUID,
        user_id: UUID,
    ) -> SubProjectMember | None:
        result = await self._session.scalar(
            select(SubProjectMember).where(
                SubProjectMember.sub_project_id == sub_project_id,
                SubProjectMember.user_id == user_id,
            ),
        )
        return result if isinstance(result, SubProjectMember) else None

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

    async def sum_approved_budget(
        self,
        *,
        main_project_id: UUID,
        excluding_sub_project_id: UUID,
    ) -> Decimal:
        value = await self._session.scalar(
            select(func.coalesce(func.sum(SubProject.budget), 0)).where(
                SubProject.main_project_id == main_project_id,
                SubProject.id != excluding_sub_project_id,
                SubProject.status.in_(
                    [
                        SubProjectStatus.not_started,
                        SubProjectStatus.in_progress,
                        SubProjectStatus.completed,
                        SubProjectStatus.closed,
                    ],
                ),
            ),
        )
        return Decimal(value or 0)

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

    async def phase_completion_counts(self, sub_project_id: UUID) -> tuple[int, int]:
        total = await self._session.scalar(
            select(func.count()).select_from(Phase).where(Phase.sub_project_id == sub_project_id),
        )
        incomplete = await self._session.scalar(
            select(func.count()).select_from(Phase).where(
                Phase.sub_project_id == sub_project_id,
                Phase.status != PhaseStatus.completed,
            ),
        )
        return int(total or 0), int(incomplete or 0)

    def add(self, sub_project: SubProject) -> None:
        self._session.add(sub_project)

    def add_review(self, review: ProjectReview) -> None:
        self._session.add(review)

    def add_phase(self, phase: Phase) -> None:
        self._session.add(phase)

    def add_member(self, member: SubProjectMember) -> None:
        self._session.add(member)

    def add_handover(self, handover: SubProjectHandover) -> None:
        self._session.add(handover)

    async def delete_member(self, member: SubProjectMember) -> None:
        await self._session.delete(member)

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
        members: Sequence[SubProjectMember] | None = None,
        handovers: Sequence[SubProjectHandover] | None = None,
        users: Sequence[User] | None = None,
        next_sequences: dict[UUID, int] | None = None,
    ) -> None:
        self.main_projects = list(main_projects)
        self.sub_projects = list(sub_projects or [])
        self.members = list(members or [])
        self.handovers = list(handovers or [])
        self.users = list(users or [])
        self.reviews: list[ProjectReview] = []
        self.phases: list[Phase] = []
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
                or self._has_member(sub_project_id=sub_project.id, user_id=actor.id)
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

    async def get_user(self, user_id: UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        members = [member for member in self.members if member.sub_project_id == sub_project_id]
        return sorted(
            members,
            key=lambda member: (member.role_in_project.value, member.joined_at),
        )

    async def list_active_sub_projects_for_leader(self, user_id: UUID) -> list[SubProject]:
        active = [
            sub_project
            for sub_project in self.sub_projects
            if sub_project.manager_id == user_id and sub_project.status in ACTIVE_HANDOVER_STATUSES
        ]
        return sorted(active, key=lambda sub_project: sub_project.created_at, reverse=True)

    async def list_sub_project_handovers(
        self,
        *,
        page: int,
        page_size: int,
        sub_project_id: UUID | None = None,
        from_user_id: UUID | None = None,
        to_user_id: UUID | None = None,
    ) -> tuple[list[SubProjectHandover], int]:
        filtered = [
            handover
            for handover in self.handovers
            if (sub_project_id is None or handover.sub_project_id == sub_project_id)
            and (from_user_id is None or handover.from_user_id == from_user_id)
            and (to_user_id is None or handover.to_user_id == to_user_id)
        ]
        ordered = sorted(filtered, key=lambda handover: handover.operated_at, reverse=True)
        start = (page - 1) * page_size
        return ordered[start : start + page_size], len(ordered)

    async def get_member(
        self,
        *,
        sub_project_id: UUID,
        user_id: UUID,
    ) -> SubProjectMember | None:
        return next(
            (
                member
                for member in self.members
                if member.sub_project_id == sub_project_id and member.user_id == user_id
            ),
            None,
        )

    async def next_sub_project_sequence(self, main_project_id: UUID) -> int:
        sequence = self.next_sequences.get(main_project_id, 1)
        self.next_sequences[main_project_id] = sequence + 1
        return sequence

    async def sum_approved_budget(
        self,
        *,
        main_project_id: UUID,
        excluding_sub_project_id: UUID,
    ) -> Decimal:
        return sum(
            (
                sub_project.budget
                for sub_project in self.sub_projects
                if sub_project.main_project_id == main_project_id
                and sub_project.id != excluding_sub_project_id
                and sub_project.status
                in {
                    SubProjectStatus.not_started,
                    SubProjectStatus.in_progress,
                    SubProjectStatus.completed,
                    SubProjectStatus.closed,
                }
            ),
            Decimal("0.00"),
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

    async def phase_completion_counts(self, sub_project_id: UUID) -> tuple[int, int]:
        phases = [phase for phase in self.phases if phase.sub_project_id == sub_project_id]
        incomplete = [phase for phase in phases if phase.status != PhaseStatus.completed]
        return len(phases), len(incomplete)

    def add(self, sub_project: SubProject) -> None:
        self.sub_projects.append(sub_project)

    def add_review(self, review: ProjectReview) -> None:
        self.reviews.append(review)

    def add_phase(self, phase: Phase) -> None:
        self.phases.append(phase)

    def add_member(self, member: SubProjectMember) -> None:
        self.members.append(member)

    def add_handover(self, handover: SubProjectHandover) -> None:
        self.handovers.append(handover)

    async def delete_member(self, member: SubProjectMember) -> None:
        self.members.remove(member)

    async def commit(self) -> None:
        return None

    async def refresh(self, sub_project: SubProject) -> None:
        return None

    def _has_member(self, *, sub_project_id: UUID, user_id: UUID) -> bool:
        return any(
            member.sub_project_id == sub_project_id and member.user_id == user_id
            for member in self.members
        )


class SubProjectService:
    def __init__(
        self,
        *,
        repository: SubProjectRepository,
        notification_service: NotificationService | None = None,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._notification_service = notification_service
        self._today_provider = today_provider

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
        await self._ensure_visible(actor, sub_project)
        return sub_project

    async def list_sub_project_members(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
    ) -> list[SubProjectMember]:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        await self._ensure_visible(actor, sub_project)
        return await self._repository.list_members(sub_project.id)

    async def add_sub_project_member(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        payload: SubProjectMemberCreate,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> SubProjectMember:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        self._ensure_project_leader(actor, sub_project)

        user = await self._repository.get_user(payload.user_id)
        if user is None:
            raise ResourceNotFoundError("用户不存在")
        if user.status != UserStatus.active or user.role != UserRole.proj_member:
            raise BusinessException(
                code=3003,
                message="只能添加活跃项目参与人",
                status_code=409,
                data={"status": user.status.value, "role": user.role.value},
            )
        existing = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=payload.user_id,
        )
        if existing is not None:
            raise ResourceConflictError("成员已存在")

        now = datetime.now(UTC)
        member = SubProjectMember(
            id=uuid4(),
            sub_project_id=sub_project.id,
            user_id=payload.user_id,
            role_in_project=SubProjectMemberRole.proj_member,
            joined_at=now,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_member(member)
        await self._repository.commit()
        self._record_member_audit(
            action="sub_project_member.add",
            actor=actor,
            member=member,
            before_state={},
            after_state=to_audit_state(member),
            audit_writer=audit_writer,
            audit_context=audit_context,
        )
        return member

    async def remove_sub_project_member(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        user_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> SubProjectMember:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        self._ensure_project_leader(actor, sub_project)
        member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=user_id,
        )
        if member is None:
            raise ResourceNotFoundError("成员关系不存在")
        if member.user_id == actor.id or member.role_in_project == SubProjectMemberRole.proj_leader:
            raise BusinessException(
                code=3003,
                message="不能移除子项目负责人",
                status_code=409,
                data={"user_id": str(user_id)},
            )

        before_state = to_audit_state(member)
        await self._repository.delete_member(member)
        await self._repository.commit()
        self._record_member_audit(
            action="sub_project_member.remove",
            actor=actor,
            member=member,
            before_state=before_state,
            after_state={},
            audit_writer=audit_writer,
            audit_context=audit_context,
        )
        return member

    async def list_active_sub_projects_for_leader(
        self,
        *,
        actor: User,
        user_id: UUID,
    ) -> list[SubProject]:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()
        return await self._repository.list_active_sub_projects_for_leader(user_id)

    async def list_sub_project_handovers(
        self,
        *,
        actor: User,
        page: int = 1,
        page_size: int = 20,
        sub_project_id: UUID | None = None,
        from_user_id: UUID | None = None,
        to_user_id: UUID | None = None,
    ) -> tuple[list[SubProjectHandover], int]:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()
        return await self._repository.list_sub_project_handovers(
            page=page,
            page_size=page_size,
            sub_project_id=sub_project_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
        )

    async def handover_sub_project(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        payload: SubProjectHandoverRequest,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
        expected_from_user_id: UUID | None = None,
    ) -> SubProject:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()

        sub_project = await self._get_existing_sub_project(sub_project_id)
        if sub_project.status not in ACTIVE_HANDOVER_STATUSES:
            raise self._invalid_status(sub_project.status.value, "当前状态不允许转交负责人")
        if expected_from_user_id is not None and sub_project.manager_id != expected_from_user_id:
            raise BusinessException(
                code=3003,
                message="子项目当前负责人不匹配",
                status_code=409,
                data={
                    "sub_project_id": str(sub_project.id),
                    "expected_from_user_id": str(expected_from_user_id),
                    "actual_manager_id": str(sub_project.manager_id),
                },
            )
        if payload.to_user_id == sub_project.manager_id:
            raise BusinessException(
                code=3003,
                message="新负责人不能与原负责人相同",
                status_code=409,
                data={"to_user_id": str(payload.to_user_id)},
            )

        from_user = await self._repository.get_user(sub_project.manager_id)
        to_user = await self._repository.get_user(payload.to_user_id)
        if to_user is None:
            raise ResourceNotFoundError("新负责人不存在")
        if to_user.role != UserRole.proj_leader or to_user.status != UserStatus.active:
            raise BusinessException(
                code=3003,
                message="新负责人必须是活跃项目负责人",
                status_code=409,
                data={"status": to_user.status.value, "role": to_user.role.value},
            )

        now = datetime.now(UTC)
        before_state = to_audit_state(sub_project)
        old_manager_id = sub_project.manager_id
        sub_project.manager_id = to_user.id
        await self._upsert_handover_members(
            sub_project=sub_project,
            old_manager_id=old_manager_id,
            new_manager_id=to_user.id,
            now=now,
        )
        self._repository.add_handover(
            SubProjectHandover(
                id=uuid4(),
                sub_project_id=sub_project.id,
                from_user_id=old_manager_id,
                to_user_id=to_user.id,
                reason=payload.reason,
                operator_id=actor.id,
                operated_at=now,
                created_at=now,
                updated_at=now,
            ),
        )
        await self._repository.commit()
        await self._repository.refresh(sub_project)

        member_ids = await self._active_member_ids(sub_project.id)
        receivers = [to_user.id, *member_ids]
        if from_user is not None and from_user.status != UserStatus.disabled:
            receivers.insert(0, from_user.id)
        await self._send_notification(
            scenario="handover_completed",
            receivers=receivers,
            source_id=sub_project.id,
            payload={
                "project_no": sub_project.project_no,
                "project_name": sub_project.name,
                "from_user_id": str(old_manager_id),
                "to_user_id": str(to_user.id),
                "reason": payload.reason,
            },
        )
        self._record_audit(
            action="sub_project.handover",
            actor=actor,
            sub_project=sub_project,
            before_state=before_state,
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={
                "from_user_id": str(old_manager_id),
                "to_user_id": str(to_user.id),
                "reason": payload.reason,
            },
        )
        return sub_project

    async def batch_handover_sub_projects(
        self,
        *,
        actor: User,
        from_user_id: UUID,
        payload: Sequence[SubProjectBatchHandoverItem],
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> list[SubProject]:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()
        return [
            await self.handover_sub_project(
                actor=actor,
                sub_project_id=item.sub_project_id,
                payload=SubProjectHandoverRequest(
                    to_user_id=item.to_user_id,
                    reason=item.reason,
                ),
                expected_from_user_id=from_user_id,
                audit_writer=audit_writer,
                audit_context=audit_context,
            )
            for item in payload
        ]

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
        self._repository.add_member(
            SubProjectMember(
                id=uuid4(),
                sub_project_id=sub_project.id,
                user_id=actor.id,
                role_in_project=SubProjectMemberRole.proj_leader,
                joined_at=now,
                created_at=now,
                updated_at=now,
            ),
        )
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

    async def submit_sub_project(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> SubProject:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        if sub_project.creator_id != actor.id:
            raise PermissionDeniedError()
        if sub_project.status not in {SubProjectStatus.pending_review, SubProjectStatus.rejected}:
            raise self._invalid_status(sub_project.status.value, "当前状态不允许提交子项目")

        before_state = to_audit_state(sub_project)
        sub_project.status = SubProjectStatus.pending_review
        await self._repository.commit()
        await self._repository.refresh(sub_project)

        receivers = await self._repository.list_active_user_ids_by_role(UserRole.dept_manager)
        await self._send_notification(
            scenario="project_pending_review",
            receivers=receivers,
            source_id=sub_project.id,
            payload={
                "project_no": sub_project.project_no,
                "project_name": sub_project.name,
            },
        )
        self._record_audit(
            action="sub_project.submit",
            actor=actor,
            sub_project=sub_project,
            before_state=before_state,
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={},
        )
        return sub_project

    async def review_sub_project(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        payload: SubProjectReviewRequest,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> SubProject:
        if actor.role not in {UserRole.admin, UserRole.dept_manager}:
            raise PermissionDeniedError()

        sub_project = await self._get_existing_sub_project(sub_project_id)
        if sub_project.creator_id == actor.id:
            raise PermissionDeniedError()
        if sub_project.status != SubProjectStatus.pending_review:
            raise self._invalid_status(sub_project.status.value, "当前状态不允许审核子项目")

        main_project = await self._get_existing_main_project(sub_project.main_project_id)
        before_state = to_audit_state(sub_project)
        over_budget_data = await self._validate_over_budget(
            main_project=main_project,
            sub_project=sub_project,
            payload=payload,
        )
        from_status = sub_project.status
        if payload.decision == ProjectReviewDecision.approve:
            sub_project.status = SubProjectStatus.in_progress
            self._create_default_phases(sub_project_id=sub_project.id, actor_id=actor.id)
        else:
            sub_project.status = SubProjectStatus.rejected

        now = datetime.now(UTC)
        review = ProjectReview(
            id=uuid4(),
            main_project_id=None,
            sub_project_id=sub_project.id,
            reviewer_id=actor.id,
            decision=payload.decision,
            from_status=MainProjectStatus(from_status.value),
            to_status=MainProjectStatus.in_progress
            if sub_project.status == SubProjectStatus.in_progress
            else MainProjectStatus.rejected,
            review_comment=payload.review_comment,
            modified_fields={},
            admin_override=actor.role == UserRole.admin,
            reviewed_at=now,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_review(review)
        await self._repository.commit()
        await self._repository.refresh(sub_project)

        await self._send_notification(
            scenario="project_review_result",
            receivers=[sub_project.manager_id],
            source_id=sub_project.id,
            payload={
                "project_no": sub_project.project_no,
                "project_name": sub_project.name,
                "decision": payload.decision.value,
                "review_comment": payload.review_comment,
            },
        )
        self._record_audit(
            action="sub_project.review",
            actor=actor,
            sub_project=sub_project,
            before_state=before_state,
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={
                "admin_override": actor.role == UserRole.admin,
                "decision": payload.decision.value,
                "over_budget_warning": over_budget_data is not None,
                "over_budget_reason": payload.over_budget_reason,
            },
        )
        return sub_project

    async def close_sub_project(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> SubProject:
        if actor.role != UserRole.dept_manager:
            raise PermissionDeniedError()

        sub_project = await self._get_existing_sub_project(sub_project_id)
        if sub_project.status == SubProjectStatus.closed:
            return sub_project
        if sub_project.status != SubProjectStatus.in_progress:
            raise self._invalid_status(sub_project.status.value, "当前状态不允许结项子项目")

        phase_count, incomplete_count = await self._repository.phase_completion_counts(
            sub_project.id,
        )
        if phase_count != 6 or incomplete_count > 0:
            raise BusinessException(
                code=3003,
                message="6 个环节全部完成后才能结项子项目",
                status_code=409,
                data={"phase_count": phase_count, "incomplete_phase_count": incomplete_count},
            )

        before_state = to_audit_state(sub_project)
        sub_project.status = SubProjectStatus.closed
        sub_project.actual_end_date = self._today_provider()
        await self._repository.commit()
        await self._repository.refresh(sub_project)
        self._record_audit(
            action="sub_project.close",
            actor=actor,
            sub_project=sub_project,
            before_state=before_state,
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={
                "phase_count": phase_count,
                "incomplete_phase_count": incomplete_count,
            },
        )
        return sub_project

    async def terminate_sub_project(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        payload: SubProjectTerminateRequest,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> SubProject:
        if actor.role not in {UserRole.admin, UserRole.dept_manager}:
            raise PermissionDeniedError()

        sub_project = await self._get_existing_sub_project(sub_project_id)
        if sub_project.status in {SubProjectStatus.closed, SubProjectStatus.terminated}:
            raise self._invalid_status(sub_project.status.value, "当前状态不允许中止子项目")

        before_state = to_audit_state(sub_project)
        sub_project.status = SubProjectStatus.terminated
        sub_project.actual_end_date = self._today_provider()
        await self._repository.commit()
        await self._repository.refresh(sub_project)
        self._record_audit(
            action="sub_project.terminate",
            actor=actor,
            sub_project=sub_project,
            before_state=before_state,
            audit_writer=audit_writer,
            audit_context=audit_context,
            extra={"reason": payload.reason},
        )
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

    async def _ensure_visible(self, actor: User, sub_project: SubProject) -> None:
        if actor.role in VIEW_ALL_SUB_PROJECT_ROLES or sub_project.manager_id == actor.id:
            return
        member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=actor.id,
        )
        if member is not None:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _ensure_project_leader(actor: User, sub_project: SubProject) -> None:
        if actor.role == UserRole.proj_leader and sub_project.manager_id == actor.id:
            return
        raise PermissionDeniedError()

    async def _upsert_handover_members(
        self,
        *,
        sub_project: SubProject,
        old_manager_id: UUID,
        new_manager_id: UUID,
        now: datetime,
    ) -> None:
        old_member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=old_manager_id,
        )
        if old_member is not None:
            old_member.role_in_project = SubProjectMemberRole.proj_member

        new_member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=new_manager_id,
        )
        if new_member is not None:
            new_member.role_in_project = SubProjectMemberRole.proj_leader
            return

        self._repository.add_member(
            SubProjectMember(
                id=uuid4(),
                sub_project_id=sub_project.id,
                user_id=new_manager_id,
                role_in_project=SubProjectMemberRole.proj_leader,
                joined_at=now,
                created_at=now,
                updated_at=now,
            ),
        )

    async def _active_member_ids(self, sub_project_id: UUID) -> list[UUID]:
        active_user_ids: list[UUID] = []
        for member in await self._repository.list_members(sub_project_id):
            user = await self._repository.get_user(member.user_id)
            if user is not None and user.status != UserStatus.disabled:
                active_user_ids.append(member.user_id)
        return active_user_ids

    async def _validate_over_budget(
        self,
        *,
        main_project: MainProject,
        sub_project: SubProject,
        payload: SubProjectReviewRequest,
    ) -> dict[str, str] | None:
        if payload.decision != ProjectReviewDecision.approve:
            return None

        current_allocated = await self._repository.sum_approved_budget(
            main_project_id=main_project.id,
            excluding_sub_project_id=sub_project.id,
        )
        new_total = current_allocated + sub_project.budget
        if new_total <= main_project.total_budget:
            return None

        over_budget_amount = new_total - main_project.total_budget
        data = {
            "budget": f"{main_project.total_budget:.2f}",
            "current_allocated": f"{current_allocated:.2f}",
            "this_amount": f"{sub_project.budget:.2f}",
            "over_budget_amount": f"{over_budget_amount:.2f}",
        }
        if payload.confirm_over_budget and payload.over_budget_reason:
            return data
        raise BusinessException(
            code=3001,
            message="子项目预算超出主项目剩余预算，需二次确认",
            status_code=409,
            data=data,
        )

    def _create_default_phases(self, *, sub_project_id: UUID, actor_id: UUID) -> None:
        now = datetime.now(UTC)
        for phase_no, code, name in DEFAULT_PHASES:
            self._repository.add_phase(
                Phase(
                    id=uuid4(),
                    sub_project_id=sub_project_id,
                    phase_no=phase_no,
                    code=code,
                    name=name,
                    status=PhaseStatus.in_progress
                    if phase_no in {1, 5}
                    else PhaseStatus.waiting,
                    enter_at=now if phase_no in {1, 5} else None,
                    finish_at=None,
                    procurement_type=None,
                    created_at=now,
                    updated_at=now,
                ),
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
    def _record_audit(
        *,
        action: str,
        actor: User,
        sub_project: SubProject,
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
                target_type="sub_project",
                target_id=str(sub_project.id),
                before_state=before_state,
                after_state=to_audit_state(sub_project),
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra=extra,
                request_id=context.request_id,
            ),
        )

    @staticmethod
    def _record_member_audit(
        *,
        action: str,
        actor: User,
        member: SubProjectMember,
        before_state: dict[str, object],
        after_state: dict[str, object],
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id or actor.id,
                action=action,
                target_type="sub_project_member",
                target_id=str(member.id),
                before_state=before_state,
                after_state=after_state,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra={"sub_project_id": str(member.sub_project_id)},
                request_id=context.request_id,
            ),
        )

    @staticmethod
    def _invalid_status(status: str, message: str) -> BusinessException:
        return BusinessException(
            code=3003,
            message=message,
            status_code=409,
            data={"status": status},
        )
