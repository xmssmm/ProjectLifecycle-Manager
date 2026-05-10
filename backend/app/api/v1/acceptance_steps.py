from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.acceptance_steps import AcceptanceStep
from app.models.users import User
from app.schemas.acceptance_steps import (
    AcceptanceStepCreate,
    AcceptanceStepListRead,
    AcceptanceStepRead,
    AcceptanceStepUpdate,
)
from app.services.acceptance_steps import (
    AcceptanceStepService,
    SqlAlchemyAcceptanceStepRepository,
)

router = APIRouter(prefix="/phases/{phase_id}/acceptance-steps", tags=["acceptance-steps"])


async def get_acceptance_step_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AcceptanceStepService:
    return AcceptanceStepService(repository=SqlAlchemyAcceptanceStepRepository(session))


def serialize_step(step: AcceptanceStep) -> dict[str, object]:
    return AcceptanceStepRead.model_validate(step).model_dump(mode="json")


@router.get("")
async def list_acceptance_steps(
    phase_id: UUID,
    service: Annotated[AcceptanceStepService, Depends(get_acceptance_step_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    steps = await service.list_steps(actor=current_user, phase_id=phase_id)
    payload = AcceptanceStepListRead(
        items=[AcceptanceStepRead.model_validate(step) for step in steps],
        total=len(steps),
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("")
async def create_acceptance_step(
    phase_id: UUID,
    payload: AcceptanceStepCreate,
    service: Annotated[AcceptanceStepService, Depends(get_acceptance_step_service)],
    current_user: Annotated[User, Depends(require_permission("acceptance_step.create"))],
) -> dict[str, object]:
    step = await service.create_step(actor=current_user, phase_id=phase_id, payload=payload)
    return success_response(serialize_step(step))


@router.put("/{step_id}")
async def update_acceptance_step(
    phase_id: UUID,
    step_id: UUID,
    payload: AcceptanceStepUpdate,
    service: Annotated[AcceptanceStepService, Depends(get_acceptance_step_service)],
    current_user: Annotated[User, Depends(require_permission("acceptance_step.complete"))],
) -> dict[str, object]:
    step = await service.update_step(
        actor=current_user,
        phase_id=phase_id,
        step_id=step_id,
        payload=payload,
    )
    return success_response(serialize_step(step))
