from __future__ import annotations

from datetime import date
from importlib import import_module
from types import ModuleType

import pytest

from app.services.audit import AuditPartitionSpec


def load_partition_module() -> ModuleType:
    try:
        return import_module("app.services.audit_partitions")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.services.audit_partitions is required: {exc}")


@pytest.mark.asyncio
async def test_partition_maintenance_creates_current_and_next_three_months_idempotently() -> None:
    partition_module = load_partition_module()
    repository = partition_module.InMemoryAuditPartitionRepository(
        existing_partitions={"audit_logs_202605"},
    )
    service = partition_module.AuditPartitionMaintenanceService(
        repository=repository,
        on_date_provider=lambda: date(2026, 5, 10),
        months_ahead=3,
    )

    first_result = await service.ensure_future_partitions()
    second_result = await service.ensure_future_partitions()

    assert first_result.ensured_partitions == [
        "audit_logs_202605",
        "audit_logs_202606",
        "audit_logs_202607",
        "audit_logs_202608",
    ]
    assert first_result.created_partitions == [
        "audit_logs_202606",
        "audit_logs_202607",
        "audit_logs_202608",
    ]
    assert second_result.ensured_partitions == first_result.ensured_partitions
    assert second_result.created_partitions == []
    assert repository.ensure_calls == [
        first_result.ensured_partitions,
        first_result.ensured_partitions,
    ]


def test_partition_create_sql_is_safe_and_idempotent() -> None:
    partition_module = load_partition_module()
    sql = partition_module.build_create_partition_sql(
        AuditPartitionSpec(
            name="audit_logs_202606",
            start=date(2026, 6, 1),
            end=date(2026, 7, 1),
        ),
    )

    assert sql == (
        'CREATE TABLE IF NOT EXISTS "audit_logs_202606" PARTITION OF audit_logs '
        "FOR VALUES FROM ('2026-06-01') TO ('2026-07-01')"
    )
    with pytest.raises(ValueError):
        partition_module.build_create_partition_sql(
            AuditPartitionSpec(
                name='audit_logs_202606"; DROP TABLE audit_logs; --',
                start=date(2026, 6, 1),
                end=date(2026, 7, 1),
            ),
        )


def test_celery_beat_schedules_audit_partition_maintenance_monthly_0030() -> None:
    from app.tasks.celery_app import create_celery_app
    from app.tasks.task_names import AUDIT_PARTITION_TASK_NAME

    celery_app = create_celery_app()

    schedule = celery_app.conf.beat_schedule["audit-partition-maintenance-monthly-0030"]
    assert schedule["task"] == AUDIT_PARTITION_TASK_NAME
    assert "30 0 1 * *" in str(schedule["schedule"])
