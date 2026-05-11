from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.external.v1.deps import ExternalApiContext, require_external_permission
from app.core.db import get_db_session
from app.core.responses import success_response
from app.models.documents import Document

router = APIRouter(tags=["external-api"])


class ExternalDocumentRead(BaseModel):
    id: UUID
    doc_no: str
    sub_project_id: UUID
    doc_type: str
    file_name: str
    file_size: int
    version: int
    is_latest: bool
    scan_status: str
    created_at: datetime
    updated_at: datetime


class ExternalDocumentListRead(BaseModel):
    items: list[ExternalDocumentRead]
    total: int


class ExternalDocumentReader(Protocol):
    async def list_documents(self) -> Sequence[ExternalDocumentRead | dict[str, object]]:
        ...


class SqlAlchemyExternalDocumentReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_documents(self) -> list[ExternalDocumentRead]:
        result = await self._session.scalars(
            select(Document)
            .where(Document.is_deleted.is_(False))
            .order_by(Document.created_at.desc()),
        )
        return [
            ExternalDocumentRead(
                id=document.id,
                doc_no=document.doc_no,
                sub_project_id=document.sub_project_id,
                doc_type=document.doc_type,
                file_name=document.file_name,
                file_size=document.file_size,
                version=document.version,
                is_latest=document.is_latest,
                scan_status=document.scan_status.value,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            for document in result.all()
        ]


async def get_external_document_reader(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExternalDocumentReader:
    return SqlAlchemyExternalDocumentReader(session)


@router.get("/documents")
async def list_documents(
    reader: Annotated[ExternalDocumentReader, Depends(get_external_document_reader)],
    _context: Annotated[ExternalApiContext, Depends(require_external_permission("documents:read"))],
) -> dict[str, object]:
    items = [ExternalDocumentRead.model_validate(item) for item in await reader.list_documents()]
    payload = ExternalDocumentListRead(items=items, total=len(items))
    return success_response(payload.model_dump(mode="json"))
