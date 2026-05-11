from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.search import get_search_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import ValidationFailedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.users import User, UserRole
from app.services.search import DocumentSearchResult, DocumentSearchResults
from tests.factories import UserFactory


def build_client(service: object) -> TestClient:
    user = UserFactory(role=UserRole.admin)

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> object:
        return service

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_search_service] = fake_service
    return TestClient(app)


def test_search_api_rejects_empty_query() -> None:
    class FakeSearchService:
        async def search_documents(self, **kwargs: object) -> DocumentSearchResults:
            raise ValidationFailedError("搜索关键词不能为空")

    client = build_client(FakeSearchService())

    response = client.get("/api/v1/search", params={"q": " ", "scope": "documents"})

    assert response.status_code == 422


def test_search_api_returns_document_results() -> None:
    result = DocumentSearchResult(
        document_id=uuid4(),
        file_name="meeting.txt",
        doc_type="meeting_material",
        sub_project_id=uuid4(),
        sub_project_no="Z-2026-0001-ZX-001",
        sub_project_name="子项目",
        phase_id=uuid4(),
        phase_name="立项",
        snippet="budget approval milestone",
    )

    class FakeSearchService:
        async def search_documents(self, **kwargs: object) -> DocumentSearchResults:
            assert kwargs["query"] == "budget"
            assert kwargs["scope"] == "documents"
            return DocumentSearchResults(items=[result], total=1)

    client = build_client(FakeSearchService())

    response = client.get("/api/v1/search", params={"q": "budget", "scope": "documents"})

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["items"][0]["file_name"] == "meeting.txt"
