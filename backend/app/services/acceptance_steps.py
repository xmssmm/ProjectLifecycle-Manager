from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessException,
    PermissionDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.models.acceptance_steps import AcceptanceStep, AcceptanceStepStatus
from app.models.documents import Document
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.users import User, UserRole
from app.schemas.acceptance_steps import AcceptanceStepCreate, AcceptanceStepUpdate

ACCEPTANCE_PHASE_NO = 4
ACCEPTANCE_REPORT_DOC_TYPE = "acceptance_report"
VIEW_ALL_ACCEPTANCE_ROLES = frozenset(
    {
        UserRole.admin,
        UserRole.dept_manager,
        UserRole.finance_manager,
        UserRole.proj_leader,
        UserRole.proj_member,
    },
)


class AcceptanceStepRepository(Protocol):
    async def get_phase(self, phase_id: UUID) -> Phase | None:
        ...

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        ...

    async def get_step(self, step_id: UUID) -> AcceptanceStep | None:
        ...

    async def get_step_by_no(self, *, phase_id: UUID, step_no: int) -> AcceptanceStep | None:
        ...

    async def list_steps(self, phase_id: UUID) -> list[AcceptanceStep]:
        ...

    async def count_step_reports(self, step_id: UUID) -> int:
        ...

    def add_step(self, step: AcceptanceStep) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_step(self, step: AcceptanceStep) -> None:
        ...


class SqlAlchemyAcceptanceStepRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        phase = await self._session.get(Phase, phase_id)
        return phase if isinstance(phase, Phase) else None

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        sub_project = await self._session.get(SubProject, sub_project_id)
        return sub_project if isinstance(sub_project, SubProject) else None

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        member = await self._session.scalar(
            select(SubProjectMember).where(
                SubProjectMember.sub_project_id == sub_project_id,
                SubProjectMember.user_id == user_id,
            ),
        )
        return member if isinstance(member, SubProjectMember) else None

    async def get_step(self, step_id: UUID) -> AcceptanceStep | None:
        step = await self._session.get(AcceptanceStep, step_id)
        return step if isinstance(step, AcceptanceStep) else None

    async def get_step_by_no(self, *, phase_id: UUID, step_no: int) -> AcceptanceStep | None:
        step = await self._session.scalar(
            select(AcceptanceStep).where(
                AcceptanceStep.phase_id == phase_id,
                AcceptanceStep.step_no == step_no,
            ),
        )
        return step if isinstance(step, AcceptanceStep) else None

    async def list_steps(self, phase_id: UUID) -> list[AcceptanceStep]:
        result = await self._session.scalars(
            select(AcceptanceStep)
            .where(AcceptanceStep.phase_id == phase_id)
            .order_by(AcceptanceStep.step_no.asc()),
        )
        return list(result.all())

    async def count_step_reports(self, step_id: UUID) -> int:
        result = await self._session.scalars(
            select(Document.id).where(
                Document.acceptance_step_id == step_id,
                Document.doc_type == ACCEPTANCE_REPORT_DOC_TYPE,
                Document.is_deleted.is_(False),
            ),
        )
        return len(result.all())

    def add_step(self, step: AcceptanceStep) -> None:
        self._session.add(step)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_step(self, step: AcceptanceStep) -> None:
        await self._session.refresh(step)


class InMemoryAcceptanceStepRepository:
    def __init__(
        self,
        *,
        acceptance_steps: Sequence[AcceptanceStep] | None = None,
        documents: Sequence[Document] | None = None,
        phases: Sequence[Phase] | None = None,
        sub_projects: Sequence[SubProject] | None = None,
        members: Sequence[SubProjectMember] | None = None,
    ) -> None:
        self.acceptance_steps = list(acceptance_steps or [])
        self.documents = list(documents or [])
        self.phases = list(phases or [])
        self.sub_projects = list(sub_projects or [])
        self.members = list(members or [])

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        return next((phase for phase in self.phases if phase.id == phase_id), None)

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        return next(
            (sub_project for sub_project in self.sub_projects if sub_project.id == sub_project_id),
            None,
        )

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        return next(
            (
                member
                for member in self.members
                if member.sub_project_id == sub_project_id and member.user_id == user_id
            ),
            None,
        )

    async def get_step(self, step_id: UUID) -> AcceptanceStep | None:
        return next((step for step in self.acceptance_steps if step.id == step_id), None)

    async def get_step_by_no(self, *, phase_id: UUID, step_no: int) -> AcceptanceStep | None:
        return next(
            (
                step
                for step in self.acceptance_steps
                if step.phase_id == phase_id and step.step_no == step_no
            ),
            None,
        )

    async def list_steps(self, phase_id: UUID) -> list[AcceptanceStep]:
        steps = [step for step in self.acceptance_steps if step.phase_id == phase_id]
        return sorted(steps, key=lambda step: step.step_no)

    async def count_step_reports(self, step_id: UUID) -> int:
        return len(
            [
                document
                for document in self.documents
                if document.acceptance_step_id == step_id
                and document.doc_type == ACCEPTANCE_REPORT_DOC_TYPE
                and not document.is_deleted
            ],
        )

    def add_step(self, step: AcceptanceStep) -> None:
        self.acceptance_steps.append(step)

    async def commit(self) -> None:
        return None

    async def refresh_step(self, step: AcceptanceStep) -> None:
        _ = step
        return None


class AcceptanceStepService:
    def __init__(self, *, repository: AcceptanceStepRepository) -> None:
        self._repository = repository

    async def list_steps(self, *, actor: User, phase_id: UUID) -> list[AcceptanceStep]:
        phase, sub_project = await self._get_scope(phase_id)
        _ = phase
        await self._ensure_visible(actor, sub_project)
        return await self._repository.list_steps(phase_id)

    async def create_step(
        self,
        *,
        actor: User,
        phase_id: UUID,
        payload: AcceptanceStepCreate,
    ) -> AcceptanceStep:
        phase, sub_project = await self._get_scope(phase_id)
        self._ensure_can_create(actor, sub_project)
        self._ensure_phase_accepts_steps(phase)
        await self._ensure_responsible_member(
            sub_project_id=sub_project.id,
            responsible_id=payload.responsible_id,
        )
        self._ensure_step_payload(payload)
        existing = await self._repository.get_step_by_no(
            phase_id=phase.id,
            step_no=payload.step_no,
        )
        if existing is not None:
            raise ResourceConflictError("Acceptance step number already exists")

        now = datetime.now(UTC)
        step = AcceptanceStep(
            id=uuid4(),
            phase_id=phase.id,
            step_no=payload.step_no,
            step_name=payload.step_name.strip(),
            responsible_id=payload.responsible_id,
            plan_date=payload.plan_date,
            description=self._clean_optional_text(payload.description),
            status=AcceptanceStepStatus.not_started,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_step(step)
        await self._repository.commit()
        await self._repository.refresh_step(step)
        return step

    async def update_step(
        self,
        *,
        actor: User,
        phase_id: UUID,
        step_id: UUID,
        payload: AcceptanceStepUpdate,
    ) -> AcceptanceStep:
        phase, sub_project = await self._get_scope(phase_id)
        self._ensure_phase_accepts_steps(phase)
        step = await self._get_existing_step(step_id)
        if step.phase_id != phase.id:
            raise ResourceNotFoundError("Acceptance step does not exist")
        self._ensure_can_update(actor, sub_project, step)

        now = datetime.now(UTC)
        if payload.status == AcceptanceStepStatus.completed:
            await self._ensure_step_report_uploaded(step.id)
            step.completed_at = now
        else:
            step.completed_at = None
        step.status = payload.status
        step.updated_at = now
        await self._repository.commit()
        await self._repository.refresh_step(step)
        return step

    async def _get_scope(self, phase_id: UUID) -> tuple[Phase, SubProject]:
        phase = await self._repository.get_phase(phase_id)
        if phase is None:
            raise ResourceNotFoundError("Phase does not exist")
        sub_project = await self._repository.get_sub_project(phase.sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        return phase, sub_project

    async def _get_existing_step(self, step_id: UUID) -> AcceptanceStep:
        step = await self._repository.get_step(step_id)
        if step is None:
            raise ResourceNotFoundError("Acceptance step does not exist")
        return step

    async def _ensure_visible(self, actor: User, sub_project: SubProject) -> None:
        if actor.role in VIEW_ALL_ACCEPTANCE_ROLES or sub_project.manager_id == actor.id:
            return
        member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=actor.id,
        )
        if member is not None:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _ensure_can_create(actor: User, sub_project: SubProject) -> None:
        if actor.role == UserRole.admin:
            return
        if actor.role == UserRole.proj_leader and sub_project.manager_id == actor.id:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _ensure_can_update(actor: User, sub_project: SubProject, step: AcceptanceStep) -> None:
        if actor.role == UserRole.admin:
            return
        if actor.role == UserRole.proj_leader and sub_project.manager_id == actor.id:
            return
        if actor.id == step.responsible_id:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _ensure_phase_accepts_steps(phase: Phase) -> None:
        if phase.phase_no != ACCEPTANCE_PHASE_NO:
            raise BusinessException(
                code=3003,
                message="Acceptance steps can only be created on acceptance phase",
                status_code=409,
                data={"phase_no": phase.phase_no},
            )
        if phase.status != PhaseStatus.in_progress:
            raise BusinessException(
                code=3003,
                message="Acceptance phase must be in progress",
                status_code=409,
                data={"status": phase.status.value},
            )

    async def _ensure_responsible_member(
        self,
        *,
        sub_project_id: UUID,
        responsible_id: UUID,
    ) -> None:
        member = await self._repository.get_member(
            sub_project_id=sub_project_id,
            user_id=responsible_id,
        )
        if member is None:
            raise BusinessException(
                code=3003,
                message="Step responsible user must be a sub project member",
                status_code=409,
                data={"responsible_id": str(responsible_id)},
            )

    async def _ensure_step_report_uploaded(self, step_id: UUID) -> None:
        if await self._repository.count_step_reports(step_id) > 0:
            return
        raise BusinessException(
            code=3002,
            message="Acceptance report is required before completing step",
            status_code=409,
            data={
                "missing_documents": [
                    {
                        "acceptance_step_id": str(step_id),
                        "doc_type": ACCEPTANCE_REPORT_DOC_TYPE,
                        "required": ">=1",
                        "actual": 0,
                    },
                ],
            },
        )

    @staticmethod
    def _ensure_step_payload(payload: AcceptanceStepCreate) -> None:
        if payload.step_no < 1:
            raise ValidationFailedError("Step number must be positive")
        if not payload.step_name.strip():
            raise ValidationFailedError("Step name is required")

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
