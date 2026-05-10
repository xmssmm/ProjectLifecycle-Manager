from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.responses import success_response
from app.models.phases import Phase
from app.models.users import User
from app.schemas.phases import (
    PhaseCompletionRead,
    PhaseDetailRead,
    PhaseListRead,
    PhaseRead,
    PhaseRequiredDocumentRead,
)
from app.services.phases import PhaseDetail, PhaseService, SqlAlchemyPhaseRepository

router = APIRouter(prefix="/phases", tags=["phases"])


async def get_phase_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PhaseService:
    return PhaseService(repository=SqlAlchemyPhaseRepository(session))


def serialize_phase(phase: Phase) -> dict[str, object]:
    return PhaseRead.model_validate(phase).model_dump(mode="json")


def serialize_phase_detail(detail: PhaseDetail) -> dict[str, object]:
    base_payload = PhaseRead.model_validate(detail.phase).model_dump()
    payload = PhaseDetailRead(
        **base_payload,
        required_documents=[
            PhaseRequiredDocumentRead.model_validate(document)
            for document in detail.required_documents
        ],
        uploaded_documents=[],
        completion=PhaseCompletionRead(
            required_total=detail.completion.required_total,
            uploaded_total=detail.completion.uploaded_total,
            missing_doc_types=detail.completion.missing_doc_types,
        ),
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
