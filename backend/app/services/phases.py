from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, PermissionDeniedError, ResourceNotFoundError
from app.models.acceptance_steps import AcceptanceStep, AcceptanceStepStatus
from app.models.documents import Document
from app.models.phases import (
    Phase,
    PhaseDocRequirement,
    PhaseDocTemplate,
    PhaseHistory,
    PhaseStatus,
    ProcurementType,
)
from app.models.sub_projects import SubProject, SubProjectMember, SubProjectStatus
from app.models.users import User, UserRole
from app.models.workflows import WorkflowTemplateVersion
from app.services.notifications import NotificationService

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
    uploaded_documents: list[Document]
    completion: PhaseCompletion

    @classmethod
    def from_documents(
        cls,
        *,
        phase: Phase,
        required_documents: list[PhaseDocTemplate],
        uploaded_documents: list[Document],
    ) -> PhaseDetail:
        uploaded_doc_types = {document.doc_type for document in uploaded_documents}
        missing_doc_types = [
            document.doc_type
            for document in required_documents
            if document.doc_type not in uploaded_doc_types
        ]
        return cls(
            phase=phase,
            required_documents=required_documents,
            uploaded_documents=uploaded_documents,
            completion=PhaseCompletion(
                required_total=len(required_documents),
                uploaded_total=len(uploaded_documents),
                missing_doc_types=missing_doc_types,
            ),
        )

    @classmethod
    def from_required_documents(
        cls,
        *,
        phase: Phase,
        required_documents: list[PhaseDocTemplate],
    ) -> PhaseDetail:
        return cls.from_documents(
            phase=phase,
            required_documents=required_documents,
            uploaded_documents=[],
        )


@dataclass(frozen=True)
class PhasePromotionResult:
    phase: Phase
    activated_phase: Phase | None


class PhaseRepository(Protocol):
    async def list_phases(self, sub_project_id: UUID) -> list[Phase]:
        ...

    async def list_phases_for_update(self, sub_project_id: UUID) -> list[Phase]:
        ...

    async def get_phase(self, phase_id: UUID) -> Phase | None:
        ...

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        ...

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        ...

    async def list_required_doc_templates(
        self,
        *,
        phase_no: int,
        procurement_type: ProcurementType | None,
    ) -> list[PhaseDocTemplate]:
        ...

    async def get_workflow_template_version(
        self,
        version_id: UUID,
    ) -> WorkflowTemplateVersion | None:
        ...

    async def list_latest_documents(self, phase_id: UUID) -> list[Document]:
        ...

    async def list_acceptance_steps(self, phase_id: UUID) -> list[AcceptanceStep]:
        ...

    def add_history(self, history: PhaseHistory) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_phase(self, phase: Phase) -> None:
        ...

    async def refresh_sub_project(self, sub_project: SubProject) -> None:
        ...


class SqlAlchemyPhaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_phases(self, sub_project_id: UUID) -> list[Phase]:
        result = await self._session.scalars(
            select(Phase).where(Phase.sub_project_id == sub_project_id).order_by(Phase.phase_no),
        )
        return list(result.all())

    async def list_phases_for_update(self, sub_project_id: UUID) -> list[Phase]:
        result = await self._session.scalars(
            select(Phase)
            .where(Phase.sub_project_id == sub_project_id)
            .order_by(Phase.phase_no)
            .with_for_update(),
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

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        result = await self._session.scalars(
            select(SubProjectMember).where(SubProjectMember.sub_project_id == sub_project_id),
        )
        return list(result.all())

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

    async def get_workflow_template_version(
        self,
        version_id: UUID,
    ) -> WorkflowTemplateVersion | None:
        version = await self._session.get(WorkflowTemplateVersion, version_id)
        return version if isinstance(version, WorkflowTemplateVersion) else None

    async def list_latest_documents(self, phase_id: UUID) -> list[Document]:
        result = await self._session.scalars(
            select(Document)
            .where(
                Document.phase_id == phase_id,
                Document.is_latest.is_(True),
                Document.is_deleted.is_(False),
            )
            .order_by(Document.doc_type.asc(), Document.created_at.desc()),
        )
        return list(result.all())

    async def list_acceptance_steps(self, phase_id: UUID) -> list[AcceptanceStep]:
        result = await self._session.scalars(
            select(AcceptanceStep)
            .where(AcceptanceStep.phase_id == phase_id)
            .order_by(AcceptanceStep.step_no.asc()),
        )
        return list(result.all())

    def add_history(self, history: PhaseHistory) -> None:
        self._session.add(history)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_phase(self, phase: Phase) -> None:
        await self._session.refresh(phase)

    async def refresh_sub_project(self, sub_project: SubProject) -> None:
        await self._session.refresh(sub_project)


class InMemoryPhaseRepository:
    def __init__(
        self,
        *,
        phases: list[Phase] | None = None,
        phase_doc_templates: list[PhaseDocTemplate] | None = None,
        documents: list[Document] | None = None,
        acceptance_steps: list[AcceptanceStep] | None = None,
        sub_projects: list[SubProject] | None = None,
        members: list[SubProjectMember] | None = None,
        histories: list[PhaseHistory] | None = None,
        workflow_versions: list[WorkflowTemplateVersion] | None = None,
    ) -> None:
        self.phases = list(phases or [])
        self.phase_doc_templates = list(phase_doc_templates or [])
        self.documents = list(documents or [])
        self.acceptance_steps = list(acceptance_steps or [])
        self.sub_projects = list(sub_projects or [])
        self.members = list(members or [])
        self.histories = list(histories or [])
        self.workflow_versions = list(workflow_versions or [])

    async def list_phases(self, sub_project_id: UUID) -> list[Phase]:
        phases = [phase for phase in self.phases if phase.sub_project_id == sub_project_id]
        return sorted(phases, key=lambda phase: phase.phase_no)

    async def list_phases_for_update(self, sub_project_id: UUID) -> list[Phase]:
        return await self.list_phases(sub_project_id)

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

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        return [member for member in self.members if member.sub_project_id == sub_project_id]

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

    async def get_workflow_template_version(
        self,
        version_id: UUID,
    ) -> WorkflowTemplateVersion | None:
        return next(
            (version for version in self.workflow_versions if version.id == version_id),
            None,
        )

    async def list_latest_documents(self, phase_id: UUID) -> list[Document]:
        documents = [
            document
            for document in self.documents
            if document.phase_id == phase_id and document.is_latest and not document.is_deleted
        ]
        return sorted(documents, key=lambda document: (document.doc_type, document.created_at))

    async def list_acceptance_steps(self, phase_id: UUID) -> list[AcceptanceStep]:
        steps = [step for step in self.acceptance_steps if step.phase_id == phase_id]
        return sorted(steps, key=lambda step: step.step_no)

    def add_history(self, history: PhaseHistory) -> None:
        self.histories.append(history)

    async def commit(self) -> None:
        return None

    async def refresh_phase(self, phase: Phase) -> None:
        return None

    async def refresh_sub_project(self, sub_project: SubProject) -> None:
        return None


class PhaseService:
    def __init__(
        self,
        *,
        repository: PhaseRepository,
        notification_service: NotificationService | None = None,
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self._repository = repository
        self._notification_service = notification_service
        self._today_provider = today_provider or (lambda: datetime.now(UTC).date())

    async def list_phases(self, *, actor: User, sub_project_id: UUID) -> list[Phase]:
        sub_project = await self._get_existing_sub_project(sub_project_id)
        await self._ensure_visible(actor, sub_project)
        return await self._repository.list_phases(sub_project_id)

    async def get_phase(self, *, actor: User, phase_id: UUID) -> PhaseDetail:
        phase = await self._get_existing_phase(phase_id)
        sub_project = await self._get_existing_sub_project(phase.sub_project_id)
        await self._ensure_visible(actor, sub_project)
        required_documents = await self._required_documents_for_phase(phase)
        uploaded_documents = await self._repository.list_latest_documents(phase.id)
        return PhaseDetail.from_documents(
            phase=phase,
            required_documents=required_documents,
            uploaded_documents=uploaded_documents,
        )

    async def promote_phase(self, *, actor: User, phase_id: UUID) -> PhasePromotionResult:
        phase = await self._get_existing_phase(phase_id)
        sub_project = await self._get_existing_sub_project(phase.sub_project_id)
        self._ensure_can_promote(actor, sub_project)
        if phase.status != PhaseStatus.in_progress:
            raise self._invalid_status(
                phase.status.value,
                "Only in-progress phases can be promoted",
            )

        phases = await self._repository.list_phases_for_update(sub_project.id)
        required_documents = await self._required_documents_for_phase(phase)
        uploaded_documents = await self._repository.list_latest_documents(phase.id)
        self._ensure_phase_dependencies_completed(phase, phases)
        acceptance_steps = await self._repository.list_acceptance_steps(phase.id)
        if self._ensure_acceptance_steps_completed(phase, acceptance_steps):
            required_documents = [
                document
                for document in required_documents
                if document.doc_type != "acceptance_report"
            ]
        self._ensure_required_documents_uploaded(required_documents, uploaded_documents)

        now = datetime.now(UTC)
        from_status = phase.status
        phase.status = PhaseStatus.completed
        phase.finish_at = now
        phase.updated_at = now
        history = PhaseHistory(
            id=uuid4(),
            phase_id=phase.id,
            from_status=from_status,
            to_status=PhaseStatus.completed,
            changed_by_id=actor.id,
            changed_at=now,
            note="promoted",
            created_at=now,
            updated_at=now,
        )
        self._repository.add_history(history)
        activated_phase = self._activate_next_phase(phase, phases, now)
        if all(item.status == PhaseStatus.completed for item in phases):
            sub_project.status = SubProjectStatus.completed
            sub_project.actual_end_date = self._today_provider()
            sub_project.updated_at = now

        await self._repository.commit()
        await self._repository.refresh_phase(phase)
        if activated_phase is not None:
            await self._repository.refresh_phase(activated_phase)
        if sub_project.status == SubProjectStatus.completed:
            await self._repository.refresh_sub_project(sub_project)

        await self._send_phase_promoted_notification(
            sub_project=sub_project,
            phase=phase,
            activated_phase=activated_phase,
        )
        return PhasePromotionResult(phase=phase, activated_phase=activated_phase)

    async def _get_existing_phase(self, phase_id: UUID) -> Phase:
        phase = await self._repository.get_phase(phase_id)
        if phase is None:
            raise ResourceNotFoundError("Phase does not exist")
        return phase

    async def _get_existing_sub_project(self, sub_project_id: UUID) -> SubProject:
        sub_project = await self._repository.get_sub_project(sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        return sub_project

    async def _required_documents_for_phase(self, phase: Phase) -> list[PhaseDocTemplate]:
        sub_project = await self._get_existing_sub_project(phase.sub_project_id)
        if sub_project.workflow_template_version_id is not None:
            version = await self._repository.get_workflow_template_version(
                sub_project.workflow_template_version_id,
            )
            if version is not None:
                return self._required_documents_from_workflow_version(version, phase)
        return await self._repository.list_required_doc_templates(
            phase_no=phase.phase_no,
            procurement_type=phase.procurement_type,
        )

    @staticmethod
    def _required_documents_from_workflow_version(
        version: WorkflowTemplateVersion,
        phase: Phase,
    ) -> list[PhaseDocTemplate]:
        definitions = [
            definition
            for definition in version.phase_definitions
            if int(cast(int | str, definition["order"])) == phase.phase_no
            or definition["key"] == phase.code
        ]
        if not definitions:
            return []

        now = datetime.now(UTC)
        documents: list[PhaseDocTemplate] = []
        required_documents = cast(
            list[dict[str, object]],
            definitions[0].get("required_documents", []),
        )
        for document in required_documents:
            if not isinstance(document, dict):
                continue
            requirement = PhaseDocRequirement(str(document["requirement"]))
            procurement_type_value = document.get("procurement_type")
            if requirement == PhaseDocRequirement.optional:
                continue
            if (
                requirement == PhaseDocRequirement.conditional
                and procurement_type_value is not None
                and phase.procurement_type != ProcurementType(str(procurement_type_value))
            ):
                continue
            documents.append(
                PhaseDocTemplate(
                    id=uuid4(),
                    phase_no=phase.phase_no,
                    doc_type=str(document["doc_type"]),
                    requirement=requirement,
                    qty_rule=str(document["qty_rule"]),
                    procurement_type=(
                        ProcurementType(str(procurement_type_value))
                        if procurement_type_value is not None
                        else None
                    ),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            )
        return sorted(documents, key=lambda item: item.doc_type)

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

    @staticmethod
    def _ensure_can_promote(actor: User, sub_project: SubProject) -> None:
        if actor.role == UserRole.admin:
            return
        if actor.role == UserRole.proj_leader and sub_project.manager_id == actor.id:
            return
        raise PermissionDeniedError()

    def _ensure_phase_dependencies_completed(
        self,
        phase: Phase,
        phases: Sequence[Phase],
    ) -> None:
        phases_by_no = {item.phase_no: item for item in phases}
        if phase.phase_no in {2, 3, 4}:
            incomplete = [
                phase_no
                for phase_no in range(1, phase.phase_no)
                if phases_by_no.get(phase_no) is None
                or phases_by_no[phase_no].status != PhaseStatus.completed
            ]
            if incomplete:
                raise self._invalid_status(
                    phase.status.value,
                    "Previous phases must be completed first",
                    data={"incomplete_phase_nos": incomplete},
                )
        if phase.phase_no == 5:
            incomplete = [
                item.phase_no
                for item in phases
                if item.phase_no != 5 and item.status != PhaseStatus.completed
            ]
            if incomplete:
                raise self._invalid_status(
                    phase.status.value,
                    "All other phases must be completed before completing payment phase",
                    data={"incomplete_phase_nos": incomplete},
                )
        if phase.phase_no == 6:
            acceptance = phases_by_no.get(4)
            if acceptance is None or acceptance.status != PhaseStatus.completed:
                raise self._invalid_status(
                    phase.status.value,
                    "Acceptance phase must be completed before post review",
                    data={"required_phase_no": 4},
                )

    def _ensure_required_documents_uploaded(
        self,
        required_documents: Sequence[PhaseDocTemplate],
        uploaded_documents: Sequence[Document],
    ) -> None:
        uploaded_counts: dict[str, int] = {}
        for document in uploaded_documents:
            uploaded_counts[document.doc_type] = uploaded_counts.get(document.doc_type, 0) + 1

        missing = [
            {
                "doc_type": template.doc_type,
                "required": template.qty_rule,
                "actual": uploaded_counts.get(template.doc_type, 0),
            }
            for template in required_documents
            if not self._matches_qty_rule(
                qty_rule=template.qty_rule,
                actual=uploaded_counts.get(template.doc_type, 0),
            )
        ]
        if missing:
            raise BusinessException(
                code=3002,
                message="Missing required documents",
                status_code=409,
                data={"missing_documents": missing},
            )

    @staticmethod
    def _ensure_acceptance_steps_completed(
        phase: Phase,
        acceptance_steps: Sequence[AcceptanceStep],
    ) -> bool:
        if phase.phase_no != 4 or not acceptance_steps:
            return False
        incomplete = [
            step.step_no
            for step in acceptance_steps
            if step.status != AcceptanceStepStatus.completed
        ]
        if incomplete:
            raise BusinessException(
                code=3003,
                message="All acceptance steps must be completed before promoting acceptance phase",
                status_code=409,
                data={"incomplete_step_nos": incomplete},
            )
        return True

    @staticmethod
    def _matches_qty_rule(*, qty_rule: str, actual: int) -> bool:
        normalized = qty_rule.strip().lower()
        if normalized.startswith(">="):
            return actual >= int(normalized.removeprefix(">=").strip())
        if normalized.startswith("="):
            return actual >= int(normalized.removeprefix("=").strip())
        if normalized.startswith("per_payment"):
            return actual >= 1
        return actual >= 1

    @staticmethod
    def _activate_next_phase(
        phase: Phase,
        phases: Sequence[Phase],
        now: datetime,
    ) -> Phase | None:
        if phase.phase_no in {1, 2, 3}:
            next_phase_no = phase.phase_no + 1
        elif phase.phase_no == 4:
            next_phase_no = 6
        else:
            return None

        next_phase = next((item for item in phases if item.phase_no == next_phase_no), None)
        if next_phase is None or next_phase.status != PhaseStatus.waiting:
            return None
        next_phase.status = PhaseStatus.in_progress
        next_phase.enter_at = now
        next_phase.updated_at = now
        return next_phase

    async def _send_phase_promoted_notification(
        self,
        *,
        sub_project: SubProject,
        phase: Phase,
        activated_phase: Phase | None,
    ) -> None:
        if self._notification_service is None:
            return
        receivers = self._unique_receivers(
            [member.user_id for member in await self._repository.list_members(sub_project.id)]
            + [sub_project.manager_id],
        )
        await self._notification_service.send(
            scenario="phase_promoted",
            receivers=receivers,
            source_id=activated_phase.id if activated_phase is not None else phase.id,
            payload={
                "sub_project_id": str(sub_project.id),
                "completed_phase_id": str(phase.id),
                "completed_phase_no": phase.phase_no,
                "activated_phase_id": str(activated_phase.id) if activated_phase else None,
                "activated_phase_no": activated_phase.phase_no if activated_phase else None,
            },
        )

    @staticmethod
    def _unique_receivers(receivers: Sequence[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        result: list[UUID] = []
        for receiver_id in receivers:
            if receiver_id in seen:
                continue
            seen.add(receiver_id)
            result.append(receiver_id)
        return result

    @staticmethod
    def _invalid_status(
        status: str,
        message: str,
        data: dict[str, object] | None = None,
    ) -> BusinessException:
        payload: dict[str, object] = {"status": status}
        if data:
            payload.update(data)
        return BusinessException(code=3003, message=message, status_code=409, data=payload)
