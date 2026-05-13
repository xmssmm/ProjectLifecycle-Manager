from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.webhook_events import enqueue_webhook_event
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.documents import Document
from app.models.phases import Phase
from app.models.users import User
from app.schemas.phases import (
    PhaseCompletionRead,
    PhaseDetailRead,
    PhaseListRead,
    PhaseProcurementTypeUpdate,
    PhasePromotionRead,
    PhaseRead,
    PhaseRequiredDocumentRead,
    PhaseUploadedDocumentRead,
)
from app.services.notification_runtime import build_notification_service
from app.services.phases import (
    PhaseDetail,
    PhasePromotionResult,
    PhaseService,
    SqlAlchemyPhaseRepository,
)
from app.services.webhooks import WebhookEventType

router = APIRouter(prefix="/phases", tags=["phases"])


async def get_phase_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PhaseService:
    return PhaseService(
        repository=SqlAlchemyPhaseRepository(session),
        notification_service=build_notification_service(session=session),
    )


def serialize_phase(phase: Phase) -> dict[str, object]:
    return PhaseRead.model_validate(phase).model_dump(mode="json")


def serialize_uploaded_document(document: Document) -> PhaseUploadedDocumentRead:
    return PhaseUploadedDocumentRead(
        id=document.id,
        doc_type=document.doc_type,
        file_name=document.file_name,
        file_size=document.file_size,
        version=document.version,
        uploader_id=document.uploader_id,
        uploaded_at=document.created_at,
    )


def serialize_phase_detail(detail: PhaseDetail) -> dict[str, object]:
    base_payload = PhaseRead.model_validate(detail.phase).model_dump()
    payload = PhaseDetailRead(
        **base_payload,
        required_documents=[
            PhaseRequiredDocumentRead.model_validate(document)
            for document in detail.required_documents
        ],
        uploaded_documents=[
            serialize_uploaded_document(document) for document in detail.uploaded_documents
        ],
        completion=PhaseCompletionRead(
            required_total=detail.completion.required_total,
            uploaded_total=detail.completion.uploaded_total,
            missing_doc_types=detail.completion.missing_doc_types,
        ),
    )
    return payload.model_dump(mode="json")


def serialize_phase_promotion(result: PhasePromotionResult) -> dict[str, object]:
    payload = PhasePromotionRead(
        phase=PhaseRead.model_validate(result.phase),
        activated_phase=PhaseRead.model_validate(result.activated_phase)
        if result.activated_phase is not None
        else None,
    )
    return payload.model_dump(mode="json")


@router.get("")
async def list_phases(
    service: Annotated[PhaseService, Depends(get_phase_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    sub_project_id: Annotated[UUID, Query()],
) -> dict[str, object]:
    phases = await service.list_phases(actor=current_user, sub_project_id=sub_project_id)
    payload = PhaseListRead(
        items=[PhaseRead.model_validate(phase) for phase in phases],
        total=len(phases),
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/{phase_id}")
async def get_phase(
    phase_id: UUID,
    service: Annotated[PhaseService, Depends(get_phase_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    detail = await service.get_phase(actor=current_user, phase_id=phase_id)
    return success_response(serialize_phase_detail(detail))


@router.put("/{phase_id}/procurement-type")
async def update_procurement_type(
    phase_id: UUID,
    payload: PhaseProcurementTypeUpdate,
    service: Annotated[PhaseService, Depends(get_phase_service)],
    current_user: Annotated[User, Depends(require_permission("phase.promote"))],
) -> dict[str, object]:
    phase = await service.update_procurement_type(
        actor=current_user,
        phase_id=phase_id,
        procurement_type=payload.procurement_type,
    )
    return success_response(serialize_phase(phase))


@router.post("/{phase_id}/promote")
async def promote_phase(
    phase_id: UUID,
    service: Annotated[PhaseService, Depends(get_phase_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_permission("phase.promote"))],
) -> dict[str, object]:
    result = await service.promote_phase(actor=current_user, phase_id=phase_id)
    source_id = result.activated_phase.id if result.activated_phase is not None else result.phase.id
    await enqueue_webhook_event(
        event_type=WebhookEventType.phase_promoted,
        session=session,
        source_id=source_id,
        payload={
            "activated_phase_id": str(result.activated_phase.id)
            if result.activated_phase is not None
            else None,
            "activated_phase_no": result.activated_phase.phase_no
            if result.activated_phase is not None
            else None,
            "completed_phase_id": str(result.phase.id),
            "completed_phase_no": result.phase.phase_no,
            "sub_project_id": str(result.phase.sub_project_id),
        },
    )
    return success_response(serialize_phase_promotion(result))
