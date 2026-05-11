from __future__ import annotations

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.documents import DocumentScanStatus
from app.models.search import DocumentSearchStatus
from app.services.search import (
    DocumentSearchService,
    InMemoryDocumentSearchRepository,
)
from app.storage.base import StorageBackend
from tests.factories import DocumentFactory, PhaseFactory, SubProjectFactory, UserFactory


class RecordingStorage(StorageBackend):
    def __init__(
        self,
        files: dict[str, bytes] | None = None,
        *,
        fail_on_read: bool = False,
    ) -> None:
        self.files = files or {}
        self.fail_on_read = fail_on_read

    def save(self, *, sub_id: str, phase_id: str, filename: str, content: bytes) -> str:
        key = f"{sub_id}/{phase_id}/{filename}"
        self.files[key] = content
        return key

    def read(self, storage_key: str) -> bytes:
        if self.fail_on_read:
            raise RuntimeError("storage unavailable")
        return self.files[storage_key]

    def delete(self, storage_key: str) -> None:
        self.files.pop(storage_key, None)

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


def make_search_service(
    *,
    content: bytes = b"budget approval milestone",
    document_scan_status: DocumentScanStatus = DocumentScanStatus.clean,
    is_deleted: bool = False,
    storage_fails: bool = False,
) -> tuple[DocumentSearchService, InMemoryDocumentSearchRepository]:
    actor = UserFactory()
    sub_project = SubProjectFactory(manager_id=actor.id)
    phase = PhaseFactory(sub_project_id=sub_project.id, name="立项")
    document = DocumentFactory(
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        file_name="meeting.txt",
        file_path=f"{sub_project.id}/{phase.id}/meeting.txt",
        scan_status=document_scan_status,
        is_deleted=is_deleted,
        uploader_id=actor.id,
    )
    repository = InMemoryDocumentSearchRepository(
        documents=[document],
        phases=[phase],
        sub_projects=[sub_project],
    )
    storage = RecordingStorage({str(document.file_path): content}, fail_on_read=storage_fails)
    service = DocumentSearchService(repository=repository, storage=storage)
    return service, repository


@pytest.mark.asyncio
async def test_clean_document_indexes_and_searches_with_project_context() -> None:
    service, repository = make_search_service()
    actor = UserFactory(id=repository.sub_projects[0].manager_id)

    result = await service.index_document(repository.documents[0].id)
    search = await service.search_documents(actor=actor, query="budget", scope="documents")

    assert result.status == DocumentSearchStatus.indexed
    assert search.items[0].document_id == repository.documents[0].id
    assert search.items[0].sub_project_id == repository.sub_projects[0].id
    assert search.items[0].phase_id == repository.phases[0].id
    assert "budget" in search.items[0].snippet.lower()


@pytest.mark.asyncio
async def test_infected_and_deleted_documents_do_not_enter_search_results() -> None:
    infected_service, infected_repository = make_search_service(
        document_scan_status=DocumentScanStatus.infected,
    )
    deleted_service, deleted_repository = make_search_service(is_deleted=True)
    actor = UserFactory(id=infected_repository.sub_projects[0].manager_id)

    await infected_service.index_document(infected_repository.documents[0].id)
    await deleted_service.index_document(deleted_repository.documents[0].id)
    infected_search = await infected_service.search_documents(
        actor=actor,
        query="budget",
        scope="documents",
    )
    deleted_search = await deleted_service.search_documents(
        actor=UserFactory(id=deleted_repository.sub_projects[0].manager_id),
        query="budget",
        scope="documents",
    )

    assert infected_search.items == []
    assert deleted_search.items == []


@pytest.mark.asyncio
async def test_extraction_failure_records_failed_status_without_raising() -> None:
    service, repository = make_search_service(storage_fails=True)

    result = await service.index_document(repository.documents[0].id)

    assert result.status == DocumentSearchStatus.failed
    assert repository.entries[0].status == DocumentSearchStatus.failed
    assert "storage unavailable" in (repository.entries[0].error_message or "")


@pytest.mark.asyncio
async def test_search_rejects_empty_query() -> None:
    service, repository = make_search_service()

    with pytest.raises(ValidationFailedError):
        await service.search_documents(
            actor=UserFactory(id=repository.sub_projects[0].manager_id),
            query="  ",
            scope="documents",
        )
