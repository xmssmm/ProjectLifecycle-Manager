from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest

from app.models.project_types import ProjectType
from app.models.workflows import WorkflowTemplate, WorkflowTemplateStatus, WorkflowTemplateVersion
from app.seeds.phase_doc_templates import PHASE_DOC_TEMPLATES
from app.seeds.run import SEED_TARGETS
from app.seeds.workflow_templates import (
    DEFAULT_PROCUREMENT_PROJECT_TYPE_CODE,
    DEFAULT_PROCUREMENT_TEMPLATE_NAME,
    build_procurement_phase_definitions,
    seed_default_procurement_workflow,
)


class FakeWorkflowSeedRepository:
    def __init__(self) -> None:
        self.project_types_by_code: dict[str, ProjectType] = {}
        self.templates_by_name: dict[tuple[str, str], WorkflowTemplate] = {}
        self.versions_by_template: dict[tuple[str, int], WorkflowTemplateVersion] = {}
        self.legacy_main_project_count = 1
        self.legacy_sub_project_count = 1
        self.backfilled_project_type_id: object | None = None
        self.backfilled_workflow_template_version_id: object | None = None

    async def get_project_type_by_code(self, code: str) -> ProjectType | None:
        return self.project_types_by_code.get(code)

    def add_project_type(self, project_type: ProjectType) -> None:
        project_type.id = uuid4()
        self.project_types_by_code[project_type.code] = project_type

    async def get_template_by_name(
        self,
        *,
        project_type_id: object,
        name: str,
    ) -> WorkflowTemplate | None:
        return self.templates_by_name.get((str(project_type_id), name))

    def add_template(self, template: WorkflowTemplate) -> None:
        template.id = uuid4()
        self.templates_by_name[(str(template.project_type_id), template.name)] = template

    async def get_template_version(
        self,
        *,
        template_id: object,
        version_no: int,
    ) -> WorkflowTemplateVersion | None:
        return self.versions_by_template.get((str(template_id), version_no))

    def add_template_version(self, version: WorkflowTemplateVersion) -> None:
        version.id = uuid4()
        self.versions_by_template[(str(version.template_id), version.version_no)] = version

    async def flush(self) -> None:
        return None

    async def backfill_legacy_project_links(
        self,
        *,
        project_type_id: object,
        workflow_template_version_id: object,
    ) -> int:
        self.backfilled_project_type_id = project_type_id
        self.backfilled_workflow_template_version_id = workflow_template_version_id
        changed = self.legacy_main_project_count + self.legacy_sub_project_count
        self.legacy_main_project_count = 0
        self.legacy_sub_project_count = 0
        return changed


def test_procurement_phase_definitions_cover_existing_phase_doc_templates() -> None:
    definitions = build_procurement_phase_definitions()

    assert [definition["order"] for definition in definitions] == [1, 2, 3, 4, 5, 6]

    document_definitions = [
        cast(list[dict[str, object]], definition["required_documents"])
        for definition in definitions
    ]
    documents = [
        (
            document["doc_type"],
            document["requirement"],
            document.get("procurement_type"),
        )
        for required_documents in document_definitions
        for document in required_documents
    ]

    assert len(documents) == len(PHASE_DOC_TEMPLATES)
    assert ("meeting_material", "required", None) in documents
    assert ("supplier_quote", "conditional", "inquiry") in documents
    assert ("bid_document", "conditional", "bidding") in documents
    assert ("single_source_report", "conditional", "single_source") in documents
    assert ("post_review_report", "required", None) in documents


@pytest.mark.asyncio
async def test_seed_default_procurement_workflow_is_idempotent() -> None:
    repository = FakeWorkflowSeedRepository()

    first_inserted = await seed_default_procurement_workflow(repository)
    second_inserted = await seed_default_procurement_workflow(repository)

    assert first_inserted == 5
    assert second_inserted == 0

    project_type = repository.project_types_by_code[DEFAULT_PROCUREMENT_PROJECT_TYPE_CODE]
    assert project_type.name == "采购项目"
    assert project_type.is_builtin is True
    assert project_type.is_active is True

    template = next(iter(repository.templates_by_name.values()))
    assert template.name == DEFAULT_PROCUREMENT_TEMPLATE_NAME
    assert template.status == WorkflowTemplateStatus.published

    version = next(iter(repository.versions_by_template.values()))
    assert version.version_no == 1
    assert version.status == WorkflowTemplateStatus.published
    assert len(version.phase_definitions) == 6
    assert repository.backfilled_project_type_id == project_type.id
    assert repository.backfilled_workflow_template_version_id == version.id


def test_seed_targets_include_workflows_in_all_seed() -> None:
    assert "workflows" in SEED_TARGETS
    assert [name for name, _seed_fn in SEED_TARGETS["all"]] == [
        "deps",
        "admin",
        "phases",
        "workflows",
    ]
