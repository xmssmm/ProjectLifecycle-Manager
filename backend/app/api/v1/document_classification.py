from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.documents import get_document_service, serialize_document
from app.core.config import Settings, get_settings
from app.core.db import AsyncSessionLocal, get_db_session
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.users import User
from app.schemas.document_classification import (
    DocumentClassificationRead,
    DocumentClassificationSuggestRequest,
    DocumentTypeConfirmRequest,
)
from app.services.ai_audit import AiAuditLogger, SqlAlchemyAiAuditLogRepository
from app.services.ai_providers import AiProviderService
from app.services.audit import AuditContext, BackgroundAuditLogWriter, get_audit_context
from app.services.document_classification import (
    DocumentClassificationRequest,
    DocumentClassificationService,
    SqlAlchemyDocumentClassificationRepository,
)
from app.services.documents import DocumentService

router = APIRouter(prefix="/document-classification", tags=["document-classification"])


def get_document_classification_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentClassificationService:
    return DocumentClassificationService(
        ai_service=AiProviderService(
            audit_logger=AiAuditLogger(SqlAlchemyAiAuditLogRepository(session)),
            settings=settings,
        ),
        repository=SqlAlchemyDocumentClassificationRepository(session),
    )


@router.post("/suggestions")
async def suggest_document_type(
    background_tasks: BackgroundTasks,
    payload: DocumentClassificationSuggestRequest,
    service: Annotated[
        DocumentClassificationService,
        Depends(get_document_classification_service),
    ],
    current_user: Annotated[User, Depends(require_permission("document.upload"))],
) -> dict[str, object]:
    result = await service.suggest_document_type(
        actor=current_user,
        request=DocumentClassificationRequest(
            current_doc_type=payload.current_doc_type,
            document_id=payload.document_id,
            file_name=payload.file_name,
            phase_id=payload.phase_id,
            sub_project_id=payload.sub_project_id,
            summary=payload.summary,
        ),
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    response = DocumentClassificationRead.model_validate(result.to_dict())
    return success_response(response.model_dump(mode="json"))


@router.post("/documents/{document_id}/confirm")
async def confirm_document_type(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    payload: DocumentTypeConfirmRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: Annotated[User, Depends(require_permission("document.upload"))],
) -> dict[str, object]:
    document = await service.confirm_document_type(
        actor=current_user,
        document_id=document_id,
        doc_type=payload.doc_type,
        audit_writer=BackgroundAuditLogWriter(
            background_tasks=background_tasks,
            session_factory=AsyncSessionLocal,
        ),
        audit_context=get_audit_context() or AuditContext(actor_id=current_user.id),
    )
    return success_response(serialize_document(document))
