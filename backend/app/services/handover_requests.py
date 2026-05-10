from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessException,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.models.handover_requests import (
    HandoverRequest,
    HandoverRequestProject,
    HandoverRequestStatus,
)
from app.models.sub_projects import (
    SubProject,
    SubProjectHandover,
    SubProjectMember,
    SubProjectMemberRole,
    SubProjectStatus,
)
from app.models.users import User, UserRole, UserStatus
from app.schemas.handover_requests import (
    HandoverCandidateDecision,
    HandoverCandidateReview,
    HandoverRequestCreate,
    HandoverReviewDecision,
    HandoverReviewRequest,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter
from app.services.notifications import NotificationService

ACTIVE_HANDOVER_STATUSES = frozenset(
    {SubProjectStatus.not_started, SubProjectStatus.in_progress, SubProjectStatus.completed},
)
ADMIN_FORCE_AFTER = timedelta(days=7)


@dataclass(frozen=True)
class HandoverRequestDetail:
    request: HandoverRequest
    sub_project_ids: list[UUID]


@dataclass(frozen=True)
class CompletionNotification:
    receivers: list[UUID]
    source_id: UUID
    payload: dict[str, object]


class HandoverRequestRepository(Protocol):
    async def get_user(self, user_id: UUID) -> User | None:
        ...

    async def get_sub_project_for_update(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_member(
        self,
        *,
        sub_project_id: UUID,
        user_id: UUID,
    ) -> SubProjectMember | None:
        ...

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        ...

    async def list_active_user_ids_by_role(
        self,
        role: UserRole,
        *,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        ...

    async def get_request_for_update(self, request_id: UUID) -> HandoverRequest | None:
        ...

    async def list_request_project_ids(self, request_id: UUID) -> list[UUID]:
        ...

    async def list_requests(
        self,
        *,
        actor: User,
        status: HandoverRequestStatus | None = None,
    ) -> list[HandoverRequest]:
        ...

    def add_request(self, request: HandoverRequest) -> None:
        ...

    def add_request_project(self, project: HandoverRequestProject) -> None:
        ...

    def add_member(self, member: SubProjectMember) -> None:
        ...

    def add_handover(self, handover: SubProjectHandover) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def refresh_request(self, request: HandoverRequest) -> None:
        ...


class SqlAlchemyHandoverRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user(self, user_id: UUID) -> User | None:
        user = await self._session.get(User, user_id)
        return user if isinstance(user, User) else None

    async def get_sub_project_for_update(self, sub_project_id: UUID) -> SubProject | None:
        result = await self._session.scalar(
            select(SubProject).where(SubProject.id == sub_project_id).with_for_update(),
        )
        return result if isinstance(result, SubProject) else None

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

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        result = await self._session.scalars(
            select(SubProjectMember).where(SubProjectMember.sub_project_id == sub_project_id),
        )
        return list(result.all())

    async def list_active_user_ids_by_role(
        self,
        role: UserRole,
        *,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        conditions = [User.role == role, User.status == UserStatus.active]
        if dept_id is not None:
            conditions.append(User.dept_id == dept_id)
        result = await self._session.scalars(select(User.id).where(*conditions))
        return list(result.all())

    async def get_request_for_update(self, request_id: UUID) -> HandoverRequest | None:
        request = await self._session.scalar(
            select(HandoverRequest)
            .where(HandoverRequest.id == request_id)
            .with_for_update(),
        )
        return request if isinstance(request, HandoverRequest) else None

    async def list_request_project_ids(self, request_id: UUID) -> list[UUID]:
        result = await self._session.scalars(
            select(HandoverRequestProject.sub_project_id)
            .where(HandoverRequestProject.request_id == request_id)
            .order_by(HandoverRequestProject.created_at.asc()),
        )
        return list(result.all())

    async def list_requests(
        self,
        *,
        actor: User,
        status: HandoverRequestStatus | None = None,
    ) -> list[HandoverRequest]:
        conditions = []
        if status is not None:
            conditions.append(HandoverRequest.status == status)
        if actor.role == UserRole.dept_manager:
            visible_project = (
                select(HandoverRequestProject.id)
                .join(SubProject, SubProject.id == HandoverRequestProject.sub_project_id)
                .where(
                    HandoverRequestProject.request_id == HandoverRequest.id,
                    SubProject.dept_id == actor.dept_id,
                )
                .exists()
            )
            conditions.append(visible_project)
        elif actor.role != UserRole.admin:
            conditions.append(
                or_(
                    HandoverRequest.from_user_id == actor.id,
                    HandoverRequest.to_user_id == actor.id,
                ),
            )
        result = await self._session.scalars(
            select(HandoverRequest)
            .where(*conditions)
            .order_by(HandoverRequest.created_at.desc()),
        )
        return list(result.all())

    def add_request(self, request: HandoverRequest) -> None:
        self._session.add(request)

    def add_request_project(self, project: HandoverRequestProject) -> None:
        self._session.add(project)

    def add_member(self, member: SubProjectMember) -> None:
        self._session.add(member)

    def add_handover(self, handover: SubProjectHandover) -> None:
        self._session.add(handover)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh_request(self, request: HandoverRequest) -> None:
        await self._session.refresh(request)


class InMemoryHandoverRequestRepository:
    def __init__(
        self,
        *,
        main_projects: Sequence[object] | None = None,
        sub_projects: Sequence[SubProject] | None = None,
        members: Sequence[SubProjectMember] | None = None,
        users: Sequence[User] | None = None,
        requests: Sequence[HandoverRequest] | None = None,
        request_projects: Sequence[HandoverRequestProject] | None = None,
    ) -> None:
        _ = main_projects
        self.sub_projects = list(sub_projects or [])
        self.members = list(members or [])
        self.users = list(users or [])
        self.requests = list(requests or [])
        self.request_projects = list(request_projects or [])
        self.handovers: list[SubProjectHandover] = []

    async def get_user(self, user_id: UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    async def get_sub_project_for_update(self, sub_project_id: UUID) -> SubProject | None:
        return next(
            (project for project in self.sub_projects if project.id == sub_project_id),
            None,
        )

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

    async def list_members(self, sub_project_id: UUID) -> list[SubProjectMember]:
        return [member for member in self.members if member.sub_project_id == sub_project_id]

    async def list_active_user_ids_by_role(
        self,
        role: UserRole,
        *,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        return [
            user.id
            for user in self.users
            if user.role == role
            and user.status == UserStatus.active
            and (dept_id is None or user.dept_id == dept_id)
        ]

    async def get_request_for_update(self, request_id: UUID) -> HandoverRequest | None:
        return next((request for request in self.requests if request.id == request_id), None)

    async def list_request_project_ids(self, request_id: UUID) -> list[UUID]:
        return [
            project.sub_project_id
            for project in self.request_projects
            if project.request_id == request_id
        ]

    async def list_requests(
        self,
        *,
        actor: User,
        status: HandoverRequestStatus | None = None,
    ) -> list[HandoverRequest]:
        requests = list(self.requests)
        if status is not None:
            requests = [request for request in requests if request.status == status]
        if actor.role == UserRole.admin:
            return sorted(requests, key=lambda item: item.created_at, reverse=True)
        if actor.role == UserRole.dept_manager:
            visible_ids = {
                project.id for project in self.sub_projects if project.dept_id == actor.dept_id
            }
            requests = [
                request
                for request in requests
                if any(
                    link.request_id == request.id and link.sub_project_id in visible_ids
                    for link in self.request_projects
                )
            ]
            return sorted(requests, key=lambda item: item.created_at, reverse=True)
        requests = [
            request
            for request in requests
            if request.from_user_id == actor.id or request.to_user_id == actor.id
        ]
        return sorted(requests, key=lambda item: item.created_at, reverse=True)

    def add_request(self, request: HandoverRequest) -> None:
        self.requests.append(request)

    def add_request_project(self, project: HandoverRequestProject) -> None:
        self.request_projects.append(project)

    def add_member(self, member: SubProjectMember) -> None:
        self.members.append(member)

    def add_handover(self, handover: SubProjectHandover) -> None:
        self.handovers.append(handover)

    async def commit(self) -> None:
        return None

    async def refresh_request(self, request: HandoverRequest) -> None:
        _ = request
        return None


class HandoverRequestService:
    def __init__(
        self,
        *,
        repository: HandoverRequestRepository,
        notification_service: NotificationService | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._notification_service = notification_service
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def list_requests(
        self,
        *,
        actor: User,
        status: HandoverRequestStatus | None = None,
    ) -> list[HandoverRequestDetail]:
        requests = await self._repository.list_requests(actor=actor, status=status)
        return [await self._detail(request) for request in requests]

    async def submit_request(
        self,
        *,
        actor: User,
        payload: HandoverRequestCreate,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> HandoverRequestDetail:
        if actor.role != UserRole.proj_leader:
            raise PermissionDeniedError()
        sub_project_ids = self._deduplicate_ids(payload.sub_project_ids)
        if payload.to_user_id == actor.id:
            raise BusinessException(
                code=3003,
                message="Candidate cannot be the current project leader",
                status_code=409,
                data={"to_user_id": str(payload.to_user_id)},
            )
        to_user = await self._get_active_project_leader(payload.to_user_id)
        projects = [
            await self._get_existing_project_for_update(project_id)
            for project_id in sub_project_ids
        ]
        for project in projects:
            self._ensure_active_project(project)
            if project.manager_id != actor.id:
                raise PermissionDeniedError()

        now = self._now_provider()
        request = HandoverRequest(
            id=uuid4(),
            from_user_id=actor.id,
            to_user_id=to_user.id,
            reason=payload.reason,
            status=HandoverRequestStatus.pending_candidate,
            candidate_comment=None,
            candidate_responded_at=None,
            reviewer_id=None,
            review_comment=None,
            reviewed_at=None,
            forced_by_id=None,
            forced_at=None,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_request(request)
        for project_id in sub_project_ids:
            self._repository.add_request_project(
                HandoverRequestProject(
                    id=uuid4(),
                    request_id=request.id,
                    sub_project_id=project_id,
                    created_at=now,
                    updated_at=now,
                ),
            )
        await self._repository.commit()
        await self._repository.refresh_request(request)
        await self._send_notification(
            scenario="handover_request_candidate",
            receivers=[to_user.id],
            source_id=request.id,
            payload={"request_id": str(request.id), "reason": request.reason},
        )
        self._record_audit(
            audit_writer=audit_writer,
            audit_context=audit_context,
            actor=actor,
            action="handover_request.create",
            request=request,
            sub_project_ids=sub_project_ids,
        )
        return HandoverRequestDetail(request=request, sub_project_ids=sub_project_ids)

    async def review_candidate(
        self,
        *,
        actor: User,
        request_id: UUID,
        payload: HandoverCandidateReview,
    ) -> HandoverRequestDetail:
        request = await self._get_existing_request_for_update(request_id)
        if actor.id != request.to_user_id:
            raise PermissionDeniedError()
        if request.status != HandoverRequestStatus.pending_candidate:
            raise self._invalid_request_status(request.status)

        now = self._now_provider()
        request.candidate_comment = self._clean_optional_text(payload.comment)
        request.candidate_responded_at = now
        request.updated_at = now
        sub_project_ids = await self._repository.list_request_project_ids(request.id)
        if payload.decision == HandoverCandidateDecision.reject:
            request.status = HandoverRequestStatus.candidate_rejected
            receivers = [request.from_user_id]
            scenario = "handover_request_rejected"
        else:
            request.status = HandoverRequestStatus.pending_review
            receivers = await self._reviewer_receivers(sub_project_ids)
            scenario = "handover_request_pending_review"
        await self._repository.commit()
        await self._repository.refresh_request(request)
        await self._send_notification(
            scenario=scenario,
            receivers=receivers,
            source_id=request.id,
            payload={"request_id": str(request.id), "decision": payload.decision.value},
        )
        return HandoverRequestDetail(request=request, sub_project_ids=sub_project_ids)

    async def review_request(
        self,
        *,
        actor: User,
        request_id: UUID,
        payload: HandoverReviewRequest,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> HandoverRequestDetail:
        request = await self._get_existing_request_for_update(request_id)
        if request.status != HandoverRequestStatus.pending_review:
            raise self._invalid_request_status(request.status)
        sub_project_ids = await self._repository.list_request_project_ids(request.id)
        projects = [
            await self._get_existing_project_for_update(project_id)
            for project_id in sub_project_ids
        ]
        self._ensure_can_review(actor, projects)

        now = self._now_provider()
        request.reviewer_id = actor.id
        request.review_comment = self._clean_optional_text(payload.review_comment)
        request.reviewed_at = now
        request.updated_at = now
        if payload.decision == HandoverReviewDecision.reject:
            request.status = HandoverRequestStatus.review_rejected
            await self._repository.commit()
            await self._repository.refresh_request(request)
            await self._send_notification(
                scenario="handover_request_rejected",
                receivers=[request.from_user_id, request.to_user_id],
                source_id=request.id,
                payload={"request_id": str(request.id), "decision": payload.decision.value},
            )
        else:
            request.status = HandoverRequestStatus.approved
            completion_notifications = await self._apply_transfer(
                request=request,
                actor=actor,
                projects=projects,
                now=now,
            )
            await self._repository.commit()
            await self._repository.refresh_request(request)
            await self._send_completion_notifications(completion_notifications)
        self._record_audit(
            audit_writer=audit_writer,
            audit_context=audit_context,
            actor=actor,
            action="handover_request.review",
            request=request,
            sub_project_ids=sub_project_ids,
        )
        return HandoverRequestDetail(request=request, sub_project_ids=sub_project_ids)

    async def force_request(
        self,
        *,
        actor: User,
        request_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> HandoverRequestDetail:
        if actor.role != UserRole.admin:
            raise PermissionDeniedError()
        request = await self._get_existing_request_for_update(request_id)
        if request.status != HandoverRequestStatus.pending_candidate:
            raise self._invalid_request_status(request.status)
        now = self._now_provider()
        if now - request.created_at < ADMIN_FORCE_AFTER:
            raise BusinessException(
                code=3003,
                message="Candidate confirmation timeout has not elapsed",
                status_code=409,
                data={"request_id": str(request.id)},
            )
        sub_project_ids = await self._repository.list_request_project_ids(request.id)
        projects = [
            await self._get_existing_project_for_update(project_id)
            for project_id in sub_project_ids
        ]
        request.status = HandoverRequestStatus.forced
        request.forced_by_id = actor.id
        request.forced_at = now
        request.updated_at = now
        completion_notifications = await self._apply_transfer(
            request=request,
            actor=actor,
            projects=projects,
            now=now,
        )
        await self._repository.commit()
        await self._repository.refresh_request(request)
        await self._send_completion_notifications(completion_notifications)
        self._record_audit(
            audit_writer=audit_writer,
            audit_context=audit_context,
            actor=actor,
            action="handover_request.force",
            request=request,
            sub_project_ids=sub_project_ids,
        )
        return HandoverRequestDetail(request=request, sub_project_ids=sub_project_ids)

    async def _apply_transfer(
        self,
        *,
        request: HandoverRequest,
        actor: User,
        projects: Sequence[SubProject],
        now: datetime,
    ) -> list[CompletionNotification]:
        to_user = await self._get_active_project_leader(request.to_user_id)
        notifications: list[CompletionNotification] = []
        for project in projects:
            self._ensure_active_project(project)
            if project.manager_id != request.from_user_id:
                raise BusinessException(
                    code=3003,
                    message="Sub project manager no longer matches handover request",
                    status_code=409,
                    data={"sub_project_id": str(project.id)},
                )
            old_manager_id = project.manager_id
            project.manager_id = to_user.id
            project.updated_at = now
            await self._upsert_members(
                sub_project_id=project.id,
                old_manager_id=old_manager_id,
                new_manager_id=to_user.id,
                now=now,
            )
            self._repository.add_handover(
                SubProjectHandover(
                    id=uuid4(),
                    sub_project_id=project.id,
                    from_user_id=old_manager_id,
                    to_user_id=to_user.id,
                    reason=request.reason,
                    operator_id=actor.id,
                    operated_at=now,
                    created_at=now,
                    updated_at=now,
                ),
            )
            member_ids = [
                member.user_id
                for member in await self._repository.list_members(project.id)
            ]
            notifications.append(
                CompletionNotification(
                    receivers=self._unique_receivers([old_manager_id, to_user.id, *member_ids]),
                    source_id=project.id,
                    payload={
                        "project_no": project.project_no,
                        "project_name": project.name,
                        "from_user_id": str(old_manager_id),
                        "to_user_id": str(to_user.id),
                        "reason": request.reason,
                    },
                ),
            )
        return notifications

    async def _send_completion_notifications(
        self,
        notifications: Sequence[CompletionNotification],
    ) -> None:
        for notification in notifications:
            await self._send_notification(
                scenario="handover_completed",
                receivers=notification.receivers,
                source_id=notification.source_id,
                payload=notification.payload,
            )

    async def _upsert_members(
        self,
        *,
        sub_project_id: UUID,
        old_manager_id: UUID,
        new_manager_id: UUID,
        now: datetime,
    ) -> None:
        old_member = await self._repository.get_member(
            sub_project_id=sub_project_id,
            user_id=old_manager_id,
        )
        if old_member is not None:
            old_member.role_in_project = SubProjectMemberRole.proj_member
            old_member.updated_at = now
        new_member = await self._repository.get_member(
            sub_project_id=sub_project_id,
            user_id=new_manager_id,
        )
        if new_member is None:
            self._repository.add_member(
                SubProjectMember(
                    id=uuid4(),
                    sub_project_id=sub_project_id,
                    user_id=new_manager_id,
                    role_in_project=SubProjectMemberRole.proj_leader,
                    joined_at=now,
                    created_at=now,
                    updated_at=now,
                ),
            )
            return
        new_member.role_in_project = SubProjectMemberRole.proj_leader
        new_member.updated_at = now

    async def _reviewer_receivers(self, sub_project_ids: Sequence[UUID]) -> list[UUID]:
        receivers = await self._repository.list_active_user_ids_by_role(UserRole.admin)
        dept_ids = {
            (await self._get_existing_project_for_update(project_id)).dept_id
            for project_id in sub_project_ids
        }
        for dept_id in dept_ids:
            receivers.extend(
                await self._repository.list_active_user_ids_by_role(
                    UserRole.dept_manager,
                    dept_id=dept_id,
                ),
            )
        return self._unique_receivers(receivers)

    async def _detail(self, request: HandoverRequest) -> HandoverRequestDetail:
        return HandoverRequestDetail(
            request=request,
            sub_project_ids=await self._repository.list_request_project_ids(request.id),
        )

    async def _get_existing_request_for_update(self, request_id: UUID) -> HandoverRequest:
        request = await self._repository.get_request_for_update(request_id)
        if request is None:
            raise ResourceNotFoundError("Handover request does not exist")
        return request

    async def _get_existing_project_for_update(self, sub_project_id: UUID) -> SubProject:
        project = await self._repository.get_sub_project_for_update(sub_project_id)
        if project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        return project

    async def _get_active_project_leader(self, user_id: UUID) -> User:
        user = await self._repository.get_user(user_id)
        if user is None:
            raise ResourceNotFoundError("User does not exist")
        if user.role != UserRole.proj_leader or user.status != UserStatus.active:
            raise BusinessException(
                code=3003,
                message="Candidate must be an active project leader",
                status_code=409,
                data={"user_id": str(user_id)},
            )
        return user

    @staticmethod
    def _ensure_active_project(project: SubProject) -> None:
        if project.status in ACTIVE_HANDOVER_STATUSES:
            return
        raise BusinessException(
            code=3003,
            message="Sub project status does not allow handover",
            status_code=409,
            data={"status": project.status.value},
        )

    @staticmethod
    def _ensure_can_review(actor: User, projects: Sequence[SubProject]) -> None:
        if actor.role == UserRole.admin:
            return
        if actor.role == UserRole.dept_manager and all(
            project.dept_id == actor.dept_id for project in projects
        ):
            return
        raise PermissionDeniedError()

    @staticmethod
    def _deduplicate_ids(values: Sequence[UUID]) -> list[UUID]:
        deduplicated = list(dict.fromkeys(values))
        if not deduplicated:
            raise ValidationFailedError("At least one sub project is required")
        return deduplicated

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _invalid_request_status(status: HandoverRequestStatus) -> BusinessException:
        return BusinessException(
            code=3003,
            message="Handover request status does not allow this action",
            status_code=409,
            data={"status": status.value},
        )

    async def _send_notification(
        self,
        *,
        scenario: str,
        receivers: Sequence[UUID],
        source_id: UUID,
        payload: dict[str, object],
    ) -> None:
        if self._notification_service is None:
            return
        await self._notification_service.send(
            scenario=scenario,
            receivers=self._unique_receivers(receivers),
            source_id=source_id,
            payload=payload,
        )

    @staticmethod
    def _unique_receivers(receivers: Sequence[UUID]) -> list[UUID]:
        return list(dict.fromkeys(receivers))

    @staticmethod
    def _record_audit(
        *,
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
        actor: User,
        action: str,
        request: HandoverRequest,
        sub_project_ids: Sequence[UUID],
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=actor.id,
                action=action,
                target_type="handover_request",
                target_id=str(request.id),
                before_state={},
                after_state={
                    "id": str(request.id),
                    "status": request.status.value,
                    "sub_project_ids": [str(project_id) for project_id in sub_project_ids],
                },
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra={
                    "from_user_id": str(request.from_user_id),
                    "to_user_id": str(request.to_user_id),
                    "reason": request.reason,
                },
                request_id=context.request_id,
            ),
        )
