from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Table, UniqueConstraint

from app.models.base import Base
from app.models.phases import (
    Phase,
    PhaseDocRequirement,
    PhaseDocTemplate,
    PhaseHistory,
    PhaseStatus,
    ProcurementType,
)
from app.schemas.phases import PhaseDocTemplateRead, PhaseHistoryRead, PhaseRead


def test_phase_enums_are_closed_sets() -> None:
    assert [status.value for status in PhaseStatus] == [
        "waiting",
        "in_progress",
        "completed",
        "revoked",
    ]
    assert [procurement_type.value for procurement_type in ProcurementType] == [
        "inquiry",
        "bidding",
        "single_source",
    ]
    assert [requirement.value for requirement in PhaseDocRequirement] == [
        "required",
        "conditional",
        "optional",
    ]
    status_type = Phase.__table__.c.status.type
    assert isinstance(status_type, SqlEnum)
    assert status_type.enums == [status.value for status in PhaseStatus]


def test_phase_tables_have_required_columns_and_constraints() -> None:
    assert "phases" in Base.metadata.tables
    assert "phase_doc_templates" in Base.metadata.tables
    assert "phase_history" in Base.metadata.tables

    phase_columns = set(Phase.__table__.c.keys())
    template_columns = set(PhaseDocTemplate.__table__.c.keys())
    history_columns = set(PhaseHistory.__table__.c.keys())

    assert {
        "id",
        "sub_project_id",
        "phase_no",
        "code",
        "name",
        "status",
        "enter_at",
        "finish_at",
        "procurement_type",
    }.issubset(phase_columns)
    assert {
        "phase_no",
        "doc_type",
        "requirement",
        "qty_rule",
        "procurement_type",
        "is_active",
    }.issubset(template_columns)
    assert {"phase_id", "from_status", "to_status", "changed_by_id", "changed_at"}.issubset(
        history_columns,
    )

    phase_table = Phase.__table__
    assert isinstance(phase_table, Table)
    unique_constraints = {
        tuple(constraint.columns.keys())
        for constraint in phase_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("sub_project_id", "phase_no") in unique_constraints


def test_phase_models_serialize_from_orm_instances() -> None:
    phase_id = uuid4()
    user_id = uuid4()
    sub_project_id = uuid4()
    now = datetime.now(UTC)
    phase = Phase(
        id=phase_id,
        sub_project_id=sub_project_id,
        phase_no=2,
        code="procurement",
        name="Procurement",
        status=PhaseStatus.in_progress,
        enter_at=now,
        finish_at=None,
        procurement_type=ProcurementType.bidding,
        created_at=now,
        updated_at=now,
    )
    template = PhaseDocTemplate(
        id=uuid4(),
        phase_no=2,
        doc_type="bid_document",
        requirement=PhaseDocRequirement.conditional,
        qty_rule="=1",
        procurement_type=ProcurementType.bidding,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    history = PhaseHistory(
        id=uuid4(),
        phase_id=phase_id,
        from_status=PhaseStatus.waiting,
        to_status=PhaseStatus.in_progress,
        changed_by_id=user_id,
        changed_at=now,
        note="activated after previous phase",
        created_at=now,
        updated_at=now,
    )

    phase_payload = PhaseRead.model_validate(phase).model_dump()
    template_payload = PhaseDocTemplateRead.model_validate(template).model_dump()
    history_payload = PhaseHistoryRead.model_validate(history).model_dump()

    assert phase_payload["id"] == phase_id
    assert phase_payload["sub_project_id"] == sub_project_id
    assert phase_payload["status"] == PhaseStatus.in_progress
    assert template_payload["requirement"] == PhaseDocRequirement.conditional
    assert template_payload["procurement_type"] == ProcurementType.bidding
    assert history_payload["changed_by_id"] == user_id


def test_phase_schema_uuid_fields_are_typed() -> None:
    assert PhaseRead.model_fields["id"].annotation is UUID
    assert PhaseRead.model_fields["sub_project_id"].annotation is UUID
    assert PhaseHistoryRead.model_fields["changed_by_id"].annotation == UUID | None
