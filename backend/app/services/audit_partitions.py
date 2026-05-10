from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit import AuditPartitionSpec, build_monthly_partition_specs
from app.services.notifications import current_business_date

PARTITION_NAME_PATTERN = re.compile(r"^audit_logs_\d{6}$")


@dataclass(frozen=True)
class AuditPartitionMaintenanceResult:
    ensured_partitions: list[str]
    created_partitions: list[str]

    def to_dict(self) -> dict[str, list[str]]:
        return asdict(self)


class AuditPartitionRepository(Protocol):
    async def ensure_partitions(self, specs: Sequence[AuditPartitionSpec]) -> list[str]:
        ...


class SqlAlchemyAuditPartitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_partitions(self, specs: Sequence[AuditPartitionSpec]) -> list[str]:
        created_partitions: list[str] = []
        for spec in specs:
            existed = await self._partition_exists(spec.name)
            await self._session.execute(text(build_create_partition_sql(spec)))
            if not existed:
                created_partitions.append(spec.name)
        await self._session.commit()
        return created_partitions

    async def _partition_exists(self, partition_name: str) -> bool:
        existing = await self._session.scalar(
            text("SELECT to_regclass(:partition_name)"),
            {"partition_name": partition_name},
        )
        return existing is not None


class InMemoryAuditPartitionRepository:
    def __init__(self, *, existing_partitions: set[str] | None = None) -> None:
        self.existing_partitions = set(existing_partitions or set())
        self.ensure_calls: list[list[str]] = []

    async def ensure_partitions(self, specs: Sequence[AuditPartitionSpec]) -> list[str]:
        partition_names = [spec.name for spec in specs]
        self.ensure_calls.append(partition_names)
        created = [
            partition_name
            for partition_name in partition_names
            if partition_name not in self.existing_partitions
        ]
        self.existing_partitions.update(partition_names)
        return created


class AuditPartitionMaintenanceService:
    def __init__(
        self,
        *,
        repository: AuditPartitionRepository,
        on_date_provider: Callable[[], date] = current_business_date,
        months_ahead: int = 3,
    ) -> None:
        self._repository = repository
        self._on_date_provider = on_date_provider
        self._months_ahead = months_ahead

    async def ensure_future_partitions(self) -> AuditPartitionMaintenanceResult:
        specs = build_monthly_partition_specs(
            self._on_date_provider(),
            months_ahead=self._months_ahead,
        )
        created_partitions = await self._repository.ensure_partitions(specs)
        return AuditPartitionMaintenanceResult(
            ensured_partitions=[spec.name for spec in specs],
            created_partitions=created_partitions,
        )


def build_create_partition_sql(spec: AuditPartitionSpec) -> str:
    if PARTITION_NAME_PATTERN.fullmatch(spec.name) is None:
        raise ValueError(f"Invalid audit partition name: {spec.name}")
    return (
        f'CREATE TABLE IF NOT EXISTS "{spec.name}" PARTITION OF audit_logs '
        f"FOR VALUES FROM ('{spec.start.isoformat()}') TO ('{spec.end.isoformat()}')"
    )
