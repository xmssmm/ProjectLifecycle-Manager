from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.permissions import require_role
from app.core.responses import success_response
from app.models.users import User, UserRole
from app.schemas.audit_logs import AuditLogListRead, AuditLogRead
from app.services.audit_logs import (
    AuditLogQuery,
    AuditLogService,
    SqlAlchemyAuditLogRepository,
)

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


async def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(repository=SqlAlchemyAuditLogRepository(session))


@router.get("")
async def list_audit_logs(
    service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
    actor_id: Annotated[UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=128)] = None,
    target_type: Annotated[str | None, Query(max_length=64)] = None,
    target_id: Annotated[str | None, Query(max_length=128)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    result = await service.list_logs(
        actor=current_user,
        query=AuditLogQuery(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        ),
    )
    payload = AuditLogListRead(
        items=[AuditLogRead.model_validate(log) for log in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )
    return success_response(payload.model_dump(mode="json"))
