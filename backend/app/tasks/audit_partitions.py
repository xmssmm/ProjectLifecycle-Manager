from __future__ import annotations

import asyncio

from app.core.db import AsyncSessionLocal
from app.services.audit_partitions import (
    AuditPartitionMaintenanceService,
    SqlAlchemyAuditPartitionRepository,
)
from app.tasks.celery_app import celery_app
from app.tasks.task_names import AUDIT_PARTITION_TASK_NAME


async def run_audit_partition_maintenance() -> dict[str, list[str]]:
    async with AsyncSessionLocal() as session:
        service = AuditPartitionMaintenanceService(
            repository=SqlAlchemyAuditPartitionRepository(session),
        )
        result = await service.ensure_future_partitions()
        return result.to_dict()


@celery_app.task(name=AUDIT_PARTITION_TASK_NAME)  # type: ignore[untyped-decorator]
def ensure_audit_partitions() -> dict[str, list[str]]:
    return asyncio.run(run_audit_partition_maintenance())
