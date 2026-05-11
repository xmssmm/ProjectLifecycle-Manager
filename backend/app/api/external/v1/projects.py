from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.external.v1.deps import ExternalApiContext, require_external_permission
from app.core.db import get_db_session
from app.core.responses import success_response
from app.models.main_projects import MainProject

router = APIRouter(tags=["external-api"])


class ExternalProjectRead(BaseModel):
    id: UUID
    project_no: str
    name: str
    status: str
    total_budget: Decimal
    spent_amount: Decimal
    created_at: datetime
    updated_at: datetime


class ExternalProjectListRead(BaseModel):
    items: list[ExternalProjectRead]
    total: int


class ExternalProjectReader(Protocol):
    async def list_projects(self) -> Sequence[ExternalProjectRead | dict[str, object]]:
        ...


class SqlAlchemyExternalProjectReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_projects(self) -> list[ExternalProjectRead]:
        result = await self._session.scalars(
            select(MainProject).order_by(MainProject.created_at.desc()),
        )
        return [
            ExternalProjectRead(
                id=project.id,
                project_no=project.project_no,
                name=project.name,
                status=project.status.value,
                total_budget=project.total_budget,
                spent_amount=project.spent_amount,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
            for project in result.all()
        ]


async def get_external_project_reader(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExternalProjectReader:
    return SqlAlchemyExternalProjectReader(session)


@router.get("/projects")
async def list_projects(
    reader: Annotated[ExternalProjectReader, Depends(get_external_project_reader)],
    _context: Annotated[ExternalApiContext, Depends(require_external_permission("projects:read"))],
) -> dict[str, object]:
    items = [ExternalProjectRead.model_validate(item) for item in await reader.list_projects()]
    payload = ExternalProjectListRead(items=items, total=len(items))
    return success_response(payload.model_dump(mode="json"))
