from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.documents import Document
from app.models.phases import Phase, PhaseDocRequirement, PhaseDocTemplate
from app.models.sub_projects import SubProject
from app.models.users import User, UserRole
from app.services.ai_audit import AiAuditLogger, InMemoryAiAuditLogRepository
from app.services.ai_providers import AiProviderService
from app.services.audit import AuditContext, InMemoryAuditLogWriter
from app.services.document_classification import (
    DocumentClassificationRequest,
    DocumentClassificationService,
    InMemoryDocumentClassificationRepository,
)
from app.services.documents import DocumentService, InMemoryDocumentRepository
from app.storage.base import StorageBackend
from tests.factories import DocumentFactory, PhaseFactory, SubProjectFactory, UserFactory

NOW = datetime(2026, 6, 30, tzinfo=UTC)


class EmptyStorage(StorageBackend):
    def save(self, *, sub_id: str, phase_id: str, filename: str, content: bytes) -> str:
        _ = sub_id, phase_id, filename, content
        return "unused"

    def read(self, storage_key: str) -> bytes:
        _ = storage_key
        return b""

    def delete(self, storage_key: str) -> None:
        _ = storage_key

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


@pytest.mark.asyncio
async def test_filename_with_contract_suggests_contract_and_records_audit() -> None:
    actor = cast(User, UserFactory(role=UserRole.proj_leader))
    sub_project = cast(SubProject, SubProjectFactory(manager_id=actor.id))
    phase = cast(Phase, PhaseFactory(sub_project_id=sub_project.id))
    audit_writer = InMemoryAuditLogWriter()
    service = DocumentClassificationService(
        repository=InMemoryDocumentClassificationRepository(
            phases=[phase],
            sub_projects=[sub_project],
        ),
    )

    result = await service.suggest_document_type(
        actor=actor,
        request=DocumentClassificationRequest(
            current_doc_type="meeting_material",
            file_name="采购合同.pdf",
            phase_id=phase.id,
            sub_project_id=sub_project.id,
        ),
        audit_context=AuditContext(actor_id=actor.id),
        audit_writer=audit_writer,
    )

    assert result.suggestions[0].doc_type == "contract"
    assert result.suggestions[0].source == "rules"
    assert audit_writer.entries[0].action == "document_classification.suggest"


@pytest.mark.asyncio
async def test_single_required_template_doc_type_has_priority() -> None:
    actor = cast(User, UserFactory(role=UserRole.proj_leader))
    sub_project = cast(SubProject, SubProjectFactory(manager_id=actor.id))
    phase = cast(Phase, PhaseFactory(sub_project_id=sub_project.id))
    template = PhaseDocTemplate(
        id=uuid4(),
        phase_no=phase.phase_no,
        doc_type="acceptance_report",
        requirement=PhaseDocRequirement.required,
        qty_rule="=1",
        procurement_type=None,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    service = DocumentClassificationService(
        repository=InMemoryDocumentClassificationRepository(
            phase_doc_templates=[template],
            phases=[phase],
            sub_projects=[sub_project],
        ),
    )

    result = await service.suggest_document_type(
        actor=actor,
        request=DocumentClassificationRequest(
            current_doc_type="meeting_material",
            file_name="random-file.docx",
            phase_id=phase.id,
            sub_project_id=sub_project.id,
        ),
    )

    assert result.suggestions[0].doc_type == "acceptance_report"
    assert result.suggestions[0].confidence > 0.9


@pytest.mark.asyncio
async def test_ai_disabled_still_returns_rule_suggestion() -> None:
    actor = cast(User, UserFactory(role=UserRole.proj_leader))
    sub_project = cast(SubProject, SubProjectFactory(manager_id=actor.id))
    phase = cast(Phase, PhaseFactory(sub_project_id=sub_project.id))
    ai_service = AiProviderService(
        audit_logger=AiAuditLogger(InMemoryAiAuditLogRepository()),
        settings=Settings(ai_enabled=False),
    )
    service = DocumentClassificationService(
        ai_service=ai_service,
        repository=InMemoryDocumentClassificationRepository(
            phases=[phase],
            sub_projects=[sub_project],
        ),
    )

    result = await service.suggest_document_type(
        actor=actor,
        request=DocumentClassificationRequest(
            file_name="服务合同.pdf",
            phase_id=phase.id,
            sub_project_id=sub_project.id,
        ),
    )

    assert result.suggestions[0].doc_type == "contract"
    assert result.suggestions[0].source == "rules"


@pytest.mark.asyncio
async def test_suggestion_does_not_modify_document_before_confirmation() -> None:
    actor = cast(User, UserFactory(role=UserRole.proj_leader))
    sub_project = cast(SubProject, SubProjectFactory(manager_id=actor.id))
    phase = cast(Phase, PhaseFactory(sub_project_id=sub_project.id))
    document = cast(
        Document,
        DocumentFactory(
            doc_type="unknown",
            file_name="采购合同.pdf",
            phase_id=phase.id,
            sub_project_id=sub_project.id,
            uploader_id=actor.id,
        ),
    )
    service = DocumentClassificationService(
        repository=InMemoryDocumentClassificationRepository(
            documents=[document],
            phases=[phase],
            sub_projects=[sub_project],
        ),
    )

    result = await service.suggest_document_type(
        actor=actor,
        request=DocumentClassificationRequest(
            document_id=document.id,
            file_name="ignored.pdf",
            phase_id=phase.id,
            sub_project_id=sub_project.id,
        ),
    )

    assert result.suggestions[0].doc_type == "contract"
    assert document.doc_type == "unknown"


@pytest.mark.asyncio
async def test_confirm_document_type_updates_latest_document_and_audits_action() -> None:
    actor = cast(User, UserFactory(role=UserRole.proj_leader))
    sub_project = cast(SubProject, SubProjectFactory(manager_id=actor.id))
    phase = cast(Phase, PhaseFactory(sub_project_id=sub_project.id))
    document = cast(
        Document,
        DocumentFactory(
            doc_type="unknown",
            file_name="采购合同.pdf",
            phase_id=phase.id,
            sub_project_id=sub_project.id,
            uploader_id=actor.id,
        ),
    )
    audit_writer = InMemoryAuditLogWriter()
    service = DocumentService(
        repository=InMemoryDocumentRepository(
            documents=[document],
            phases=[phase],
            sub_projects=[sub_project],
        ),
        storage=EmptyStorage(),
        max_file_size_bytes=1024,
    )

    updated = await service.confirm_document_type(
        actor=actor,
        document_id=document.id,
        doc_type="contract",
        audit_context=AuditContext(actor_id=actor.id),
        audit_writer=audit_writer,
    )

    assert updated.doc_type == "contract"
    assert updated.version == 1
    assert audit_writer.entries[0].action == "document_classification.confirm"
