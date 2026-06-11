from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import (
    BusinessException,
    PermissionDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.models.documents import Document
from app.models.phases import Phase, PhaseHistory, PhaseStatus
from app.models.revoke_requests import (
    RevokeRequest,
    RevokeRequestStatus,
    RevokeReviewDecision,
)
from app.models.sub_projects import SubProject, SubProjectMember, SubProjectStatus
from app.models.tasks import Task
from app.models.users import User, UserRole, UserStatus
from app.schemas.revoke_requests import RevokeRequestCreate, RevokeRequestReview
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter
from app.services.notifications import NotificationService

VIEW_ALL_REVOKE_ROLES = frozenset({UserRole.admin, UserRole.dept_manager})
LOCKED_REVOKE_SUB_PROJECT_STATUSES = frozenset(
    {SubProjectStatus.completed, SubProjectStatus.closed, SubProjectStatus.terminated},
)


class RevokeRequestRepository(Protocol):
    async def get_phase(self, phase_id: UUID) -> Phase | None:
        ...

    async def get_sub_project(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_member(self, *, sub_project_id: UUID, user_id: UUID) -> SubProjectMember | None:
        ...

    async def get_pending_request_by_phase(self, phase_id: UUID) -> RevokeRequest | None:
        ...

    async def get_request_for_update(self, request_id: UUID) -> RevokeRequest | None:
        ...

    async def list_managed_sub_project_ids(self, manager_id: UUID) -> list[UUID]:
        ...

    async def list_requests(
        self,
        *,
        status: RevokeRequestStatus | None,
        sub_project_ids: Sequence[UUID] | None = None,
        requester_id: UUID | None = None,
    ) -> list[RevokeRequest]:
        ...

    async def list_active_user_ids_by_role(
        self,
        *,
        role: UserRole,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        ...

    async def list_phases_for_update(self, sub_project_id: UUID) -> list[Phase]:
        ...

    async def list_latest_documents_for_update(self, phase_id: UUID) -> list[Document]:
        ...

    async def list_phase_tasks(self, phase_id: UUID) -> list[Task]:
        ...

    def add_request(self, request: RevokeRequest) -> None:
        ...

    def add_history(self, history: PhaseHistory) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_request(self, request: RevokeRequest) -> None:
        ...

    async def refresh_phase(self, phase: Phase) -> None:
        ...


class SqlAlchemyRevokeRequestRepository:
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

    async def get_pending_request_by_phase(self, phase_id: UUID) -> RevokeRequest | None:
        request = await self._session.scalar(
            select(RevokeRequest).where(
                RevokeRequest.phase_id == phase_id,
                RevokeRequest.status == RevokeRequestStatus.pending,
            ),
        )
        return request if isinstance(request, RevokeRequest) else None

    async def get_request_for_update(self, request_id: UUID) -> RevokeRequest | None:
        request = await self._session.scalar(
            select(RevokeRequest).where(RevokeRequest.id == request_id).with_for_update(),
        )
        return request if isinstance(request, RevokeRequest) else None

    async def list_managed_sub_project_ids(self, manager_id: UUID) -> list[UUID]:
        result = await self._session.scalars(
            select(SubProject.id).where(SubProject.manager_id == manager_id),
        )
        return list(result.all())

    async def list_requests(
        self,
        *,
        status: RevokeRequestStatus | None,
        sub_project_ids: Sequence[UUID] | None = None,
        requester_id: UUID | None = None,
    ) -> list[RevokeRequest]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(RevokeRequest.status == status)

        visibility_conditions: list[ColumnElement[bool]] = []
        if sub_project_ids is not None:
            visibility_conditions.append(RevokeRequest.sub_project_id.in_(list(sub_project_ids)))
        if requester_id is not None:
            visibility_conditions.append(RevokeRequest.requester_id == requester_id)
        if visibility_conditions:
            conditions.append(or_(*visibility_conditions))

        result = await self._session.scalars(
            select(RevokeRequest).where(*conditions).order_by(RevokeRequest.created_at.desc()),
        )
        return list(result.all())

    async def list_active_user_ids_by_role(
        self,
        *,
        role: UserRole,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        conditions = [User.role == role, User.status == UserStatus.active]
        if dept_id is not None:
            conditions.append(User.dept_id == dept_id)
        result = await self._session.scalars(select(User.id).where(*conditions))
        return list(result.all())

    async def list_phases_for_update(self, sub_project_id: UUID) -> list[Phase]:
        result = await self._session.scalars(
            select(Phase)
            .where(Phase.sub_project_id == sub_project_id)
            .order_by(Phase.phase_no)
            .with_for_update(),
        )
        return list(result.all())

    async def list_latest_documents_for_update(self, phase_id: UUID) -> list[Document]:
        result = await self._session.scalars(
            select(Document)
            .where(
                Document.phase_id == phase_id,
                Document.is_latest.is_(True),
                Document.is_deleted.is_(False),
            )
            .with_for_update(),
        )
        return list(result.all())

    async def list_phase_tasks(self, phase_id: UUID) -> list[Task]:
        result = await self._session.scalars(select(Task).where(Task.phase_id == phase_id))
        return list(result.all())

    def add_request(self, request: RevokeRequest) -> None:
        self._session.add(request)

    def add_history(self, history: PhaseHistory) -> None:
        self._session.add(history)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_request(self, request: RevokeRequest) -> None:
        await self._session.refresh(request)

    async def refresh_phase(self, phase: Phase) -> None:
        await self._session.refresh(phase)


class InMemoryRevokeRequestRepository:
    def __init__(
        self,
        *,
        documents: Sequence[Document] | None = None,
        histories: Sequence[PhaseHistory] | None = None,
        members: Sequence[SubProjectMember] | None = None,
        phases: Sequence[Phase] | None = None,
        revoke_requests: Sequence[RevokeRequest] | None = None,
        sub_projects: Sequence[SubProject] | None = None,
        tasks: Sequence[Task] | None = None,
        users: Sequence[User] | None = None,
    ) -> None:
        self.documents = list(documents or [])
        self.histories = list(histories or [])
        self.members = list(members or [])
        self.phases = list(phases or [])
        self.revoke_requests = list(revoke_requests or [])
        self.sub_projects = list(sub_projects or [])
        self.tasks = list(tasks or [])
        self.users = list(users or [])

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

    async def get_pending_request_by_phase(self, phase_id: UUID) -> RevokeRequest | None:
        return next(
            (
                request
                for request in self.revoke_requests
                if request.phase_id == phase_id and request.status == RevokeRequestStatus.pending
            ),
            None,
        )

    async def get_request_for_update(self, request_id: UUID) -> RevokeRequest | None:
        return next(
            (request for request in self.revoke_requests if request.id == request_id),
            None,
        )

    async def list_managed_sub_project_ids(self, manager_id: UUID) -> list[UUID]:
        return [
            sub_project.id
            for sub_project in self.sub_projects
            if sub_project.manager_id == manager_id
        ]

    async def list_requests(
        self,
        *,
        status: RevokeRequestStatus | None,
        sub_project_ids: Sequence[UUID] | None = None,
        requester_id: UUID | None = None,
    ) -> list[RevokeRequest]:
        requests = list(self.revoke_requests)
        if status is not None:
            requests = [request for request in requests if request.status == status]
        if sub_project_ids is not None or requester_id is not None:
            visible_sub_project_ids = set(sub_project_ids or [])
            requests = [
                request
                for request in requests
                if request.sub_project_id in visible_sub_project_ids
                or (requester_id is not None and request.requester_id == requester_id)
            ]
        return sorted(requests, key=lambda request: request.created_at, reverse=True)

    async def list_active_user_ids_by_role(
        self,
        *,
        role: UserRole,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        return [
            user.id
            for user in self.users
            if user.role == role
            and user.status == UserStatus.active
            and (dept_id is None or user.dept_id == dept_id)
        ]

    async def list_phases_for_update(self, sub_project_id: UUID) -> list[Phase]:
        phases = [phase for phase in self.phases if phase.sub_project_id == sub_project_id]
        return sorted(phases, key=lambda phase: phase.phase_no)

    async def list_latest_documents_for_update(self, phase_id: UUID) -> list[Document]:
        return [
            document
            for document in self.documents
            if document.phase_id == phase_id and document.is_latest and not document.is_deleted
        ]

    async def list_phase_tasks(self, phase_id: UUID) -> list[Task]:
        return [task for task in self.tasks if task.phase_id == phase_id]

    def add_request(self, request: RevokeRequest) -> None:
        self.revoke_requests.append(request)

    def add_history(self, history: PhaseHistory) -> None:
        self.histories.append(history)

    async def commit(self) -> None:
        return None

    async def refresh_request(self, request: RevokeRequest) -> None:
        _ = request
        return None

    async def refresh_phase(self, phase: Phase) -> None:
        _ = phase
        return None


class RevokeRequestService:
    def __init__(
        self,
        *,
        repository: RevokeRequestRepository,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._repository = repository
        self._notification_service = notification_service

    async def list_requests(
        self,
        *,
        actor: User,
        status: RevokeRequestStatus | None = None,
    ) -> list[RevokeRequest]:
        if actor.role in VIEW_ALL_REVOKE_ROLES:
            return await self._repository.list_requests(status=status)
        if actor.role == UserRole.proj_leader:
            managed_ids = await self._repository.list_managed_sub_project_ids(actor.id)
            return await self._repository.list_requests(
                requester_id=actor.id,
                status=status,
                sub_project_ids=managed_ids,
            )
        raise PermissionDeniedError()

    async def submit_request(
        self,
        *,
        actor: User,
        payload: RevokeRequestCreate,
    ) -> RevokeRequest:
        reason = self._clean_reason(payload.reason)
        phase = await self._get_existing_phase(payload.phase_id)
        sub_project = await self._get_existing_sub_project(phase.sub_project_id)
        self._ensure_can_submit(actor, sub_project)
        self._ensure_phase_can_be_revoked(phase=phase, sub_project=sub_project)
        existing = await self._repository.get_pending_request_by_phase(phase.id)
        if existing is not None:
            raise ResourceConflictError("Pending revoke request already exists")

        now = datetime.now(UTC)
        request = RevokeRequest(
            id=uuid4(),
            phase_id=phase.id,
            sub_project_id=sub_project.id,
            requester_id=actor.id,
            reason=reason,
            keep_documents=payload.keep_documents,
            status=RevokeRequestStatus.pending,
            reviewer_id=None,
            review_comment=None,
            reviewed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_request(request)
        await self._repository.commit()
        await self._repository.refresh_request(request)
        await self._send_revoke_request_pending_notification(
            phase=phase,
            request=request,
            sub_project=sub_project,
        )
        return request

    async def review_request(
        self,
        *,
        actor: User,
        request_id: UUID,
        payload: RevokeRequestReview,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> RevokeRequest:
        self._ensure_can_review(actor)
        request = await self._get_existing_request_for_update(request_id)
        if request.status != RevokeRequestStatus.pending:
            raise BusinessException(
                code=3003,
                message="Only pending revoke requests can be reviewed",
                status_code=409,
                data={"status": request.status.value},
            )

        phase = await self._get_existing_phase(request.phase_id)
        sub_project = await self._get_existing_sub_project(request.sub_project_id)
        documents = await self._repository.list_latest_documents_for_update(phase.id)
        tasks = await self._repository.list_phase_tasks(phase.id)
        now = datetime.now(UTC)
        before_state = self._build_audit_state(request=request, phase=phase)

        request.reviewer_id = actor.id
        request.review_comment = self._clean_optional_text(payload.review_comment)
        request.reviewed_at = now
        request.updated_at = now
        if payload.decision == RevokeReviewDecision.reject:
            request.status = RevokeRequestStatus.rejected
        else:
            self._ensure_phase_can_be_revoked(phase=phase, sub_project=sub_project)
            request.status = RevokeRequestStatus.approved
            self._apply_approval(
                actor=actor,
                documents=documents,
                keep_documents=request.keep_documents,
                phase=phase,
                now=now,
            )

        await self._repository.commit()
        await self._repository.refresh_request(request)
        await self._repository.refresh_phase(phase)
        await self._send_revoke_result_notification(
            documents=documents,
            phase=phase,
            request=request,
            sub_project=sub_project,
        )
        self._record_review_audit(
            audit_context=audit_context,
            audit_writer=audit_writer,
            actor=actor,
            after_state=self._build_audit_state(request=request, phase=phase),
            before_state=before_state,
            documents=documents,
            request=request,
            tasks=tasks,
        )
        return request

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

    async def _get_existing_request_for_update(self, request_id: UUID) -> RevokeRequest:
        request = await self._repository.get_request_for_update(request_id)
        if request is None:
            raise ResourceNotFoundError("Revoke request does not exist")
        return request

    async def _send_revoke_result_notification(
        self,
        *,
        documents: Sequence[Document],
        phase: Phase,
        request: RevokeRequest,
        sub_project: SubProject,
    ) -> None:
        if self._notification_service is None:
            return
        receivers = self._unique_receivers(
            [sub_project.manager_id] + [document.uploader_id for document in documents],
        )
        await self._notification_service.send(
            scenario="revoke_result",
            receivers=receivers,
            source_id=request.id,
            payload={
                "decision": request.status.value,
                "phase_id": str(phase.id),
                "phase_no": phase.phase_no,
                "sub_project_id": str(sub_project.id),
            },
        )

    async def _send_revoke_request_pending_notification(
        self,
        *,
        phase: Phase,
        request: RevokeRequest,
        sub_project: SubProject,
    ) -> None:
        if self._notification_service is None:
            return
        receivers = self._unique_receivers(
            await self._repository.list_active_user_ids_by_role(role=UserRole.admin)
            + await self._repository.list_active_user_ids_by_role(
                role=UserRole.dept_manager,
                dept_id=sub_project.dept_id,
            ),
        )
        await self._notification_service.send(
            scenario="revoke_request_pending",
            receivers=receivers,
            source_id=request.id,
            payload={
                "phase_id": str(phase.id),
                "phase_no": phase.phase_no,
                "request_id": str(request.id),
                "sub_project_id": str(sub_project.id),
            },
        )

    def _apply_approval(
        self,
        *,
        actor: User,
        documents: Sequence[Document],
        keep_documents: bool,
        phase: Phase,
        now: datetime,
    ) -> None:
        from_status = phase.status
        phase.status = PhaseStatus.in_progress
        phase.finish_at = None
        phase.enter_at = phase.enter_at or now
        phase.updated_at = now
        self._repository.add_history(
            PhaseHistory(
                id=uuid4(),
                phase_id=phase.id,
                from_status=from_status,
                to_status=PhaseStatus.in_progress,
                changed_by_id=actor.id,
                changed_at=now,
                note="revoked",
                created_at=now,
                updated_at=now,
            ),
        )

        if not keep_documents:
            for document in documents:
                document.is_deleted = True
                document.updated_at = now

    @staticmethod
    def _ensure_can_submit(actor: User, sub_project: SubProject) -> None:
        if actor.role == UserRole.proj_leader and sub_project.manager_id == actor.id:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _ensure_can_review(actor: User) -> None:
        if actor.role in VIEW_ALL_REVOKE_ROLES:
            return
        raise PermissionDeniedError()

    @staticmethod
    def _ensure_phase_can_be_revoked(*, phase: Phase, sub_project: SubProject) -> None:
        if sub_project.status in LOCKED_REVOKE_SUB_PROJECT_STATUSES:
            raise BusinessException(
                code=3003,
                message="Completed or closed sub project cannot be rolled back",
                status_code=409,
                data={"status": sub_project.status.value},
            )
        if phase.status == PhaseStatus.completed:
            return
        raise BusinessException(
            code=3030,
            message="Only completed phases can be revoked",
            status_code=409,
            data={"status": phase.status.value},
        )

    @staticmethod
    def _clean_reason(reason: str) -> str:
        cleaned = reason.strip()
        if not cleaned:
            raise ValidationFailedError("Revoke reason is required")
        return cleaned

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _build_audit_state(*, request: RevokeRequest, phase: Phase) -> dict[str, object]:
        return {
            "id": str(request.id),
            "phase_id": str(phase.id),
            "phase_status": phase.status.value,
            "request_status": request.status.value,
        }

    @staticmethod
    def _record_review_audit(
        *,
        actor: User,
        after_state: dict[str, object],
        audit_context: AuditContext | None,
        audit_writer: AuditLogWriter | None,
        before_state: dict[str, object],
        documents: Sequence[Document],
        request: RevokeRequest,
        tasks: Sequence[Task],
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id,
                action="revoke_request.review",
                target_type="revoke_request",
                target_id=str(request.id),
                before_state=before_state,
                after_state=after_state,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra={
                    "document_ids_soft_deleted": [
                        str(document.id) for document in documents if not request.keep_documents
                    ],
                    "keep_documents": request.keep_documents,
                    "tasks_preserved": True,
                    "preserved_task_ids": [str(task.id) for task in tasks],
                },
                request_id=context.request_id,
            ),
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
