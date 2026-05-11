from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.services.search import DocumentSearchService, SqlAlchemyDocumentSearchRepository
from app.storage.factory import create_storage_backend
from app.tasks.celery_app import celery_app
from app.tasks.task_names import DOCUMENT_SEARCH_INDEX_TASK_NAME


class CeleryDocumentSearchScheduler:
    def enqueue(self, document_id: UUID) -> None:
        index_document_search.delay(str(document_id))


async def run_document_search_index(document_id: UUID) -> dict[str, str]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = DocumentSearchService(
            repository=SqlAlchemyDocumentSearchRepository(session),
            storage=create_storage_backend(settings),
        )
        result = await service.index_document(document_id)
        return {
            "document_id": str(result.document_id),
            "status": result.status.value,
            "error_message": result.error_message or "",
        }


@celery_app.task(name=DOCUMENT_SEARCH_INDEX_TASK_NAME)  # type: ignore[untyped-decorator]
def index_document_search(document_id: str) -> dict[str, str]:
    return asyncio.run(run_document_search_index(UUID(document_id)))
