from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Table, UniqueConstraint

from app.core.exceptions import ResourceConflictError
from app.models.project_types import ProjectType
from app.models.workflows import WorkflowTemplateStatus, WorkflowTemplateVersion
from app.schemas.workflows import WorkflowRequiredDocument, WorkflowTemplateVersionCreate


def make_phase_definition(
    *,
    key: str = "initiation",
    name: str = "立项",
    order: int = 1,
) -> dict[str, object]:
    return {
        "key": key,
        "name": name,
        "order": order,
        "required_documents": [
            {
                "doc_type": "approval_form",
                "requirement": "required",
                "qty_rule": "one",
            },
        ],
        "allow_parallel": False,
        "entry_rules": {},
    }


def test_project_type_code_is_unique() -> None:
    table = cast(Table, ProjectType.__table__)
    unique_constraints = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "uq_project_types_code" in unique_constraints


def test_template_version_schema_rejects_missing_phase_key() -> None:
    invalid_definition = make_phase_definition()
    invalid_definition.pop("key")

    with pytest.raises(ValidationError) as exc_info:
        WorkflowTemplateVersionCreate.model_validate({"phase_definitions": [invalid_definition]})

    assert "key" in str(exc_info.value)


def test_template_version_schema_rejects_duplicate_phase_keys() -> None:
    with pytest.raises(ValidationError, match="duplicate phase key"):
        WorkflowTemplateVersionCreate.model_validate(
            {
                "phase_definitions": [
                make_phase_definition(key="review", name="部门审核", order=1),
                make_phase_definition(key="review", name="复核", order=2),
                ],
            }
        )


def test_template_version_schema_requires_contiguous_order_from_one() -> None:
    with pytest.raises(ValidationError, match="phase order must start at 1 and be continuous"):
        WorkflowTemplateVersionCreate.model_validate(
            {
                "phase_definitions": [
                    make_phase_definition(key="review", name="部门审核", order=2),
                ],
            }
        )


def test_published_template_version_cannot_replace_phase_definitions() -> None:
    version = WorkflowTemplateVersion(
        template_id=uuid4(),
        version_no=1,
        status=WorkflowTemplateStatus.published,
        phase_definitions=[make_phase_definition()],
    )

    with pytest.raises(ResourceConflictError):
        version.replace_phase_definitions(
            [
                make_phase_definition(
                    key="acceptance",
                    name="验收",
                    order=1,
                ),
            ],
        )

    assert version.phase_definitions == [make_phase_definition()]


def test_draft_template_version_can_replace_phase_definitions() -> None:
    version = WorkflowTemplateVersion(
        template_id=uuid4(),
        version_no=1,
        status=WorkflowTemplateStatus.draft,
        phase_definitions=[make_phase_definition()],
    )
    replacement = [
        WorkflowRequiredDocument(
            doc_type="acceptance_report",
            requirement="required",
            qty_rule="one",
        )
    ]

    version.replace_phase_definitions(
        [
            {
                "key": "acceptance",
                "name": "验收",
                "order": 1,
                "required_documents": [item.model_dump() for item in replacement],
                "allow_parallel": False,
                "entry_rules": {},
            },
        ],
    )

    assert version.phase_definitions[0]["key"] == "acceptance"
