from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.revoke_requests import RevokeRequest, RevokeRequestStatus
from app.models.users import User
from app.schemas.revoke_requests import (
    RevokeRequestCreate,
    RevokeRequestListRead,
    RevokeRequestRead,
    RevokeRequestReview,
)
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.notification_runtime import build_notification_service
from app.services.revoke_requests import (
    RevokeRequestService,
    SqlAlchemyRevokeRequestRepository,
)

router = APIRouter(prefix="/revoke-requests", tags=["revoke-requests"])


async def get_revoke_request_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RevokeRequestService:
    return RevokeRequestService(
        notification_service=build_notification_service(session=session),
        repository=SqlAlchemyRevokeRequestRepository(session),
    )


def serialize_revoke_request(request: RevokeRequest) -> dict[str, object]:
    return RevokeRequestRead.model_validate(request).model_dump(mode="json")


@router.get("")
async def list_revoke_requests(
    service: Annotated[RevokeRequestService, Depends(get_revoke_request_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: Annotated[RevokeRequestStatus | None, Query()] = None,
) -> dict[str, object]:
    requests = await service.list_requests(actor=current_user, status=status)
    payload = RevokeRequestListRead(
        items=[RevokeRequestRead.model_validate(request) for request in requests],
        total=len(requests),
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def submit_revoke_request(
    payload: RevokeRequestCreate,
    service: Annotated[RevokeRequestService, Depends(get_revoke_request_service)],
    current_user: Annotated[User, Depends(require_permission("revoke_request.submit"))],
) -> dict[str, object]:
    request = await service.submit_request(actor=current_user, payload=payload)
    return success_response(serialize_revoke_request(request))


@router.post("/{request_id}/review")
async def review_revoke_request(
    request_id: UUID,
    payload: RevokeRequestReview,
    background_tasks: BackgroundTasks,
    service: Annotated[RevokeRequestService, Depends(get_revoke_request_service)],
    current_user: Annotated[User, Depends(require_permission("revoke_request.review"))],
) -> dict[str, object]:
    request = await service.review_request(
        actor=current_user,
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        payload=payload,
        request_id=request_id,
    )
    return success_response(serialize_revoke_request(request))
