from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.models.phases import Phase, PhaseDocRequirement, PhaseDocTemplate, ProcurementType
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.users import User, UserRole

VIEW_ALL_PHASE_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)


@dataclass(frozen=True)
class PhaseCompletion:
    required_total: int
    uploaded_total: int
    missing_doc_types: list[str]


@dataclass(frozen=True)
class PhaseDetail:
    phase: Phase
    required_documents: list[PhaseDocTemplate]
    uploaded_documents: list[object]
    completion: PhaseCompletion

    @classmethod
    def from_required_documents(
        cls,
        *,
        phase: Phase,
        required_documents: list[PhaseDocTemplate],
    ) -> PhaseDetail:
        missing_doc_types = [document.doc_type for document in required_documents]
        return cls(
            phase=phase,
            required_documents=required_documents,
            uploaded_documents=[],
            completion=PhaseCompletion(
                required_total=len(required_documents),
                uploaded_total=0,
                missing_doc_types=missing_doc_types,
            ),
        )


class PhaseRepository(Protocol):
    async def list_phases(self, sub_project_id: UUID) -> list[Phase]:
        ...

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        ...

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        ...

    async def list_required_doc_templates(
        self,
        *,
        phase_no: int,
        procurement_type: ProcurementType | None,
    ) -> list[PhaseDocTemplate]:
        ...


class SqlAlchemyPhaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_phases(self, sub_project_id: UUID) -> list[Phase]:
        result = await self._session.scalars(
            select(Phase).where(Phase.sub_project_id == sub_project_id).order_by(Phase.phase_no),
        )
        return list(result.all())

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

    async def list_required_doc_templates(
        self,
        *,
        phase_no: int,
        procurement_type: ProcurementType | None,
    ) -> list[PhaseDocTemplate]:
        conditions = [
            PhaseDocTemplate.phase_no == phase_no,
            PhaseDocTemplate.is_active.is_(True),
            or_(
                PhaseDocTemplate.requirement == PhaseDocRequirement.required,
                and_(
                    PhaseDocTemplate.requirement == PhaseDocRequirement.conditional,
                    PhaseDocTemplate.procurement_type == procurement_type,
                ),
            ),
        ]
        if procurement_type is None:
            conditions.append(PhaseDocTemplate.requirement == PhaseDocRequirement.required)

        result = await self._session.scalars(
            select(PhaseDocTemplate).where(*conditions).order_by(PhaseDocTemplate.doc_type),
        )
        return list(result.all())


class InMemoryPhaseRepository:
    def __init__(
        self,
        *,
        phases: list[Phase] | None = None,
        phase_doc_templates: list[PhaseDocTemplate] | None = None,
        sub_projects: list[SubProject] | None = None,
        members: list[SubProjectMember] | None = None,
    ) -> None:
        self.phases = list(phases or [])
        self.phase_doc_templates = list(phase_doc_templates or [])
        self.sub_projects = list(sub_projects or [])
        self.members = list(members or [])

    async def list_phases(self, sub_project_id: UUID) -> list[Phase]:
        phases = [phase for phase in self.phases if phase.sub_project_id == sub_project_id]
        return sorted(phases, key=lambda phase: phase.phase_no)

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

    async def list_required_doc_templates(
        self,
        *,
        phase_no: int,
        procurement_type: ProcurementType | None,
    ) -> list[PhaseDocTemplate]:
        templates = [
            template
            for template in self.phase_doc_templates
            if template.phase_no == phase_no
            and template.is_active
            and (
                template.requirement == PhaseDocRequirement.required
                or (
                    procurement_type is not None
                    and template.requirement == PhaseDocRequirement.conditional
                    and template.procurement_type == procurement_type
                )
            )
        ]
        return sorted(templates, key=lambda template: template.doc_type)


class PhaseService:
    def __init__(self, *, repository: PhaseRepository) -> None:
        self._repository = repository

    async def list_phases(self, *, actor: User, sub_project_id: UUID) -> list[Phase]:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        await self._ensure_visible(actor, sub_project)
        return await self._repository.list_phases(sub_project_id)

    async def get_phase(self, *, actor: User, phase_id: UUID) -> PhaseDetail:
        phase = await self._repository.get_phase(phase_id)
        if phase is None:
            raise ResourceNotFoundError("环节不存在")
        sub_project = await self._get_existing_sub_project(phase.sub_project_id)
        await self._ensure_visible(actor, sub_project)
        required_documents = await self._repository.list_required_doc_templates(
            phase_no=phase.phase_no,
            procurement_type=phase.procurement_type,
        )
        return PhaseDetail.from_required_documents(
            phase=phase,
            required_documents=required_documents,
        )

    async def _get_existing_sub_project(self, sub_project_id: UUID) -> SubProject:
        sub_project = await self._repository.get_sub_project(sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("子项目不存在")
        return sub_project

    async def _ensure_visible(self, actor: User, sub_project: SubProject) -> None:
        if actor.role in VIEW_ALL_PHASE_ROLES or sub_project.manager_id == actor.id:
            return
        member = await self._repository.get_member(
            sub_project_id=sub_project.id,
            user_id=actor.id,
        )
        if member is not None:
            return
        raise PermissionDeniedError()
