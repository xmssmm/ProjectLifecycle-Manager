from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.users import User
from app.services.ai_audit import AiAuditLogger, SqlAlchemyAiAuditLogRepository
from app.services.ai_providers import AiProviderService
from app.services.project_benchmarks import SqlAlchemyProjectBenchmarkRepository
from app.services.project_risk import ProjectRiskService

router = APIRouter(prefix="/project-risk", tags=["project-risk"])


async def get_project_risk_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProjectRiskService:
    ai_service = AiProviderService(
        audit_logger=AiAuditLogger(SqlAlchemyAiAuditLogRepository(session)),
        settings=settings,
    )
    return ProjectRiskService(
        ai_service=ai_service,
        repository=SqlAlchemyProjectBenchmarkRepository(session),
    )


@router.get("/{project_id}")
async def analyze_project_risk(
    project_id: UUID,
    service: Annotated[ProjectRiskService, Depends(get_project_risk_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    result = await service.analyze_project(actor=current_user, project_id=project_id)
    return success_response(result.to_dict())
