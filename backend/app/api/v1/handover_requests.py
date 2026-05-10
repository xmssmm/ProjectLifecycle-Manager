from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.handover_requests import HandoverRequestStatus
from app.models.users import User
from app.schemas.handover_requests import (
    HandoverCandidateReview,
    HandoverRequestCreate,
    HandoverRequestListRead,
    HandoverRequestRead,
    HandoverReviewRequest,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.handover_requests import (
    HandoverRequestDetail,
    HandoverRequestService,
    SqlAlchemyHandoverRequestRepository,
)
from app.services.notification_runtime import build_notification_service

router = APIRouter(prefix="/handover-requests", tags=["handover-requests"])


async def get_handover_request_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HandoverRequestService:
    return HandoverRequestService(
        repository=SqlAlchemyHandoverRequestRepository(session),
        notification_service=build_notification_service(session=session),
    )


def build_handover_request_read(detail: HandoverRequestDetail) -> HandoverRequestRead:
    request = detail.request
    return HandoverRequestRead(
        id=request.id,
        from_user_id=request.from_user_id,
        to_user_id=request.to_user_id,
        sub_project_ids=detail.sub_project_ids,
        reason=request.reason,
        status=request.status,
        candidate_comment=request.candidate_comment,
        candidate_responded_at=request.candidate_responded_at,
        reviewer_id=request.reviewer_id,
        review_comment=request.review_comment,
        reviewed_at=request.reviewed_at,
        forced_by_id=request.forced_by_id,
        forced_at=request.forced_at,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def serialize_handover_request(detail: HandoverRequestDetail) -> dict[str, object]:
    return build_handover_request_read(detail).model_dump(mode="json")


@router.get("")
async def list_handover_requests(
    service: Annotated[HandoverRequestService, Depends(get_handover_request_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: Annotated[HandoverRequestStatus | None, Query()] = None,
) -> dict[str, object]:
    details = await service.list_requests(actor=current_user, status=status)
    payload = HandoverRequestListRead(
        items=[build_handover_request_read(detail) for detail in details],
        total=len(details),
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def submit_handover_request(
    payload: HandoverRequestCreate,
    background_tasks: BackgroundTasks,
    service: Annotated[HandoverRequestService, Depends(get_handover_request_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    detail = await service.submit_request(
        actor=current_user,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_handover_request(detail))


@router.post("/{request_id}/candidate-review")
async def review_handover_candidate(
    request_id: UUID,
    payload: HandoverCandidateReview,
    service: Annotated[HandoverRequestService, Depends(get_handover_request_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    detail = await service.review_candidate(
        actor=current_user,
        request_id=request_id,
        payload=payload,
    )
    return success_response(serialize_handover_request(detail))


@router.post("/{request_id}/review")
async def review_handover_request(
    request_id: UUID,
    payload: HandoverReviewRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[HandoverRequestService, Depends(get_handover_request_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    detail = await service.review_request(
        actor=current_user,
        request_id=request_id,
        payload=payload,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_handover_request(detail))


@router.post("/{request_id}/force")
async def force_handover_request(
    request_id: UUID,
    background_tasks: BackgroundTasks,
    service: Annotated[HandoverRequestService, Depends(get_handover_request_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    detail = await service.force_request(
        actor=current_user,
        request_id=request_id,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_handover_request(detail))
