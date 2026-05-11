from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.users import User
from app.schemas.analytics_qa import AnalyticsQaAnswerRead, AnalyticsQaQuestionRequest
from app.services.ai_audit import AiAuditLogger, SqlAlchemyAiAuditLogRepository
from app.services.ai_providers import AiProviderService
from app.services.analytics_qa import AnalyticsQaService, SqlAlchemyAnalyticsQaQueryExecutor

router = APIRouter(prefix="/analytics-qa", tags=["analytics-qa"])


def get_analytics_qa_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalyticsQaService:
    return AnalyticsQaService(
        ai_service=AiProviderService(
            audit_logger=AiAuditLogger(SqlAlchemyAiAuditLogRepository(session)),
            settings=settings,
        ),
        query_executor=SqlAlchemyAnalyticsQaQueryExecutor(session),
    )


@router.post("/ask")
async def ask_analytics_question(
    payload: AnalyticsQaQuestionRequest,
    service: Annotated[AnalyticsQaService, Depends(get_analytics_qa_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    answer = await service.answer_question(actor=current_user, question=payload.question)
    response = AnalyticsQaAnswerRead.model_validate(answer.to_dict())
    return success_response(response.model_dump(mode="json"))
