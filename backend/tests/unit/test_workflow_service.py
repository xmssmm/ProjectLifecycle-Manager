from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.exceptions import ResourceConflictError
from app.models.users import User, UserRole, UserStatus
from app.models.workflows import WorkflowTemplateStatus, WorkflowTemplateVersion
from app.schemas.workflows import ProjectTypeCreate, WorkflowPhaseDefinitionsUpdate
from app.services.audit import InMemoryAuditLogWriter
from app.services.workflows import InMemoryWorkflowRepository, WorkflowService

NOW = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


def make_admin() -> User:
    return User(
        id=uuid4(),
        username="admin",
        email=None,
        password_hash="hashed",
        role=UserRole.admin,
        dept_id=None,
        status=UserStatus.active,
        password_changed_at=NOW,
        last_login_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_create_project_type_rejects_duplicate_code_and_writes_audit() -> None:
    repository = InMemoryWorkflowRepository(now_provider=lambda: NOW)
    service = WorkflowService(repository=repository, now_provider=lambda: NOW)
    admin = make_admin()
    audit_writer = InMemoryAuditLogWriter()

    created = await service.create_project_type(
        actor=admin,
        payload=ProjectTypeCreate(code="research", name="科研项目", description="科研流程"),
        audit_writer=audit_writer,
    )

    assert created.code == "research"
    assert audit_writer.entries[0].action == "workflow.project_type.create"

    with pytest.raises(ResourceConflictError):
        await service.create_project_type(
            actor=admin,
            payload=ProjectTypeCreate(code="research", name="重复", description=None),
            audit_writer=audit_writer,
        )


@pytest.mark.asyncio
async def test_update_draft_phase_definitions_and_publish_version() -> None:
    repository = InMemoryWorkflowRepository(now_provider=lambda: NOW)
    service = WorkflowService(repository=repository, now_provider=lambda: NOW)
    admin = make_admin()
    project_type = await service.create_project_type(
        actor=admin,
        payload=ProjectTypeCreate(code="research", name="科研项目", description=None),
    )
    template = await service.create_template(
        actor=admin,
        project_type_id=project_type.id,
        name="research-default",
        description="科研默认流程",
    )
    version = repository.versions_by_id[template.versions[0].id]

    updated = await service.update_phase_definitions(
        actor=admin,
        version_id=version.id,
        payload=WorkflowPhaseDefinitionsUpdate.model_validate(
            {
                "phase_definitions": [
                {
                    "key": "proposal",
                    "name": "课题申报",
                    "order": 1,
                    "required_documents": [],
                    "allow_parallel": False,
                    "entry_rules": {},
                },
                ],
            },
        ),
    )
    published = await service.publish_template_version(actor=admin, version_id=version.id)

    assert updated.phase_definitions[0]["key"] == "proposal"
    assert published.status == WorkflowTemplateStatus.published
    assert published.published_at == NOW

    with pytest.raises(ResourceConflictError):
        await service.update_phase_definitions(
            actor=admin,
            version_id=version.id,
            payload=WorkflowPhaseDefinitionsUpdate.model_validate(
                {"phase_definitions": updated.phase_definitions},
            ),
        )


@pytest.mark.asyncio
async def test_publish_requires_draft_with_phase_definitions() -> None:
    repository = InMemoryWorkflowRepository(now_provider=lambda: NOW)
    service = WorkflowService(repository=repository, now_provider=lambda: NOW)
    empty_version = WorkflowTemplateVersion(
        id=uuid4(),
        template_id=uuid4(),
        version_no=1,
        status=WorkflowTemplateStatus.draft,
        phase_definitions=[],
        published_at=None,
        created_at=NOW,
        updated_at=NOW,
    )
    repository.versions_by_id[empty_version.id] = empty_version

    with pytest.raises(ResourceConflictError):
        await service.publish_template_version(actor=make_admin(), version_id=empty_version.id)
