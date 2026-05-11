from __future__ import annotations

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.base import Base
from app.models.custom_reports import (
    CustomReportDefinition,
    CustomReportRun,
    CustomReportRunStatus,
    CustomReportShareScope,
)
from app.services.report_datasets import (
    DatasetAggregate,
    DatasetFilterOperator,
    default_report_dataset_registry,
)


def test_custom_report_models_are_registered() -> None:
    assert "custom_report_definitions" in Base.metadata.tables
    assert "custom_report_runs" in Base.metadata.tables
    assert [scope.value for scope in CustomReportShareScope] == [
        "private",
        "department",
        "global",
    ]
    assert [status.value for status in CustomReportRunStatus] == [
        "queued",
        "running",
        "completed",
        "failed",
    ]

    definition_columns = set(CustomReportDefinition.__table__.c.keys())
    run_columns = set(CustomReportRun.__table__.c.keys())

    assert {
        "dataset",
        "query_config",
        "share_scope",
        "schedule_frequency",
        "next_run_at",
    }.issubset(definition_columns)
    assert {"report_id", "status", "row_count", "storage_key"}.issubset(run_columns)


def test_default_report_dataset_registry_contains_required_datasets() -> None:
    registry = default_report_dataset_registry()

    assert set(registry.keys()) == {
        "project_overview",
        "task_overdue",
        "payment_execution",
        "document_upload",
        "risk_score",
    }
    for dataset_key in registry.keys():
        dataset = registry.require_dataset(dataset_key)
        assert dataset.label
        assert dataset.fields
        assert dataset.default_scope in {"project", "sub_project"}


def test_report_dataset_metadata_exposes_allowed_operations() -> None:
    registry = default_report_dataset_registry()
    dataset = registry.require_dataset("project_overview")

    status = dataset.require_field("status")
    total_budget = dataset.require_field("total_budget")

    assert DatasetFilterOperator.eq in status.filter_ops
    assert DatasetFilterOperator.in_ in status.filter_ops
    assert DatasetAggregate.sum in total_budget.aggregates
    assert DatasetAggregate.avg in total_budget.aggregates


@pytest.mark.parametrize(
    ("field", "aggregate", "operator"),
    [
        ("project_no;drop table users", None, None),
        ("project_no", DatasetAggregate.sum, None),
        ("total_budget", None, DatasetFilterOperator.contains),
    ],
)
def test_report_dataset_rejects_unregistered_or_unsupported_fields(
    field: str,
    aggregate: DatasetAggregate | None,
    operator: DatasetFilterOperator | None,
) -> None:
    registry = default_report_dataset_registry()
    dataset = registry.require_dataset("project_overview")

    with pytest.raises(ValidationFailedError):
        if aggregate is not None:
            dataset.require_metric(field, aggregate)
        elif operator is not None:
            dataset.require_filter(field, operator)
        else:
            dataset.require_field(field)
