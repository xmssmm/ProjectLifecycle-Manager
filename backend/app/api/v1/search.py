from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.core.permissions import require_permission
from app.core.responses import success_response
from app.models.users import User
from app.schemas.search import DocumentSearchResultRead, DocumentSearchResultsRead
from app.services.search import (
    DocumentSearchResults,
    DocumentSearchService,
    SqlAlchemyDocumentSearchRepository,
)
from app.storage.factory import create_storage_backend

router = APIRouter(prefix="/search", tags=["search"])


def get_search_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentSearchService:
    return DocumentSearchService(
        repository=SqlAlchemyDocumentSearchRepository(session),
        storage=create_storage_backend(settings),
    )


def serialize_search_results(results: DocumentSearchResults) -> dict[str, object]:
    payload = DocumentSearchResultsRead(
        items=[
            DocumentSearchResultRead(
                document_id=item.document_id,
                file_name=item.file_name,
                doc_type=item.doc_type,
                sub_project_id=item.sub_project_id,
                sub_project_no=item.sub_project_no,
                sub_project_name=item.sub_project_name,
                phase_id=item.phase_id,
                phase_name=item.phase_name,
                snippet=item.snippet,
            )
            for item in results.items
        ],
        total=results.total,
    )
    return payload.model_dump(mode="json")


@router.get("")
async def search(
    service: Annotated[DocumentSearchService, Depends(get_search_service)],
    current_user: Annotated[User, Depends(require_permission("document.download"))],
    q: Annotated[str, Query()],
    scope: Annotated[str, Query()] = "documents",
) -> dict[str, object]:
    results = await service.search_documents(actor=current_user, query=q, scope=scope)
    return success_response(serialize_search_results(results))
