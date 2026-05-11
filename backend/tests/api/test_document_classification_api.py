from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.document_classification import get_document_classification_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.users import User, UserRole
from app.services.audit import AuditContext, AuditLogWriter
from app.services.document_classification import (
    DocumentClassificationRequest,
    DocumentClassificationResult,
    DocumentTypeSuggestion,
)
from tests.factories import UserFactory


def test_document_classification_api_returns_suggestions() -> None:
    actor = cast(User, UserFactory(role=UserRole.admin))
    sub_project_id = uuid4()
    phase_id = uuid4()

    class FakeDocumentClassificationService:
        async def suggest_document_type(
            self,
            *,
            actor: User,
            request: DocumentClassificationRequest,
            audit_context: AuditContext | None = None,
            audit_writer: AuditLogWriter | None = None,
        ) -> DocumentClassificationResult:
            assert actor.id == actor_id
            assert request.file_name == "采购合同.pdf"
            assert request.current_doc_type == "meeting_material"
            assert audit_context is not None
            assert audit_writer is not None
            return DocumentClassificationResult(
                current_doc_type=request.current_doc_type,
                document_id=None,
                file_name=request.file_name,
                phase_id=request.phase_id,
                sub_project_id=request.sub_project_id,
                suggestions=[
                    DocumentTypeSuggestion(
                        confidence=0.9,
                        doc_type="contract",
                        reason="文件名包含「合同」",
                        source="rules",
                    ),
                ],
            )

    actor_id = actor.id
    response = build_client(actor, FakeDocumentClassificationService()).post(
        "/api/v1/document-classification/suggestions",
        json={
            "current_doc_type": "meeting_material",
            "file_name": "采购合同.pdf",
            "phase_id": str(phase_id),
            "sub_project_id": str(sub_project_id),
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["suggestions"][0]["doc_type"] == "contract"
    assert payload["phase_id"] == str(phase_id)


def build_client(user: User, service: object) -> TestClient:
    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return user

    async def fake_service() -> object:
        return service

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_document_classification_service] = fake_service
    return TestClient(app)
