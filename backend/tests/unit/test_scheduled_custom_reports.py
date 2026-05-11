from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time
from io import BytesIO
from typing import cast
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook  # type: ignore[import-untyped]

from app.models.custom_reports import (
    CustomReportDefinition,
    CustomReportRunStatus,
    CustomReportScheduleFrequency,
    CustomReportShareScope,
)
from app.models.users import User, UserRole
from app.schemas.custom_reports import CustomReportDefinitionCreate, ReportQueryConfig
from app.services.custom_reports import (
    CustomReportNotificationSender,
    CustomReportQueryExecutor,
    CustomReportService,
    InMemoryCustomReportRepository,
)
from app.services.report_query_compiler import CompiledReportQuery
from app.storage.base import StorageBackend
from tests.factories import UserFactory


@dataclass(frozen=True)
class SavedFile:
    storage_key: str
    filename: str
    content: bytes


class RecordingStorage(StorageBackend):
    def __init__(self) -> None:
        self.saved: list[SavedFile] = []

    def save(
        self,
        *,
        sub_id: str,
        phase_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        storage_key = f"{sub_id}/{phase_id}/{filename}"
        self.saved.append(SavedFile(storage_key=storage_key, filename=filename, content=content))
        return storage_key

    def read(self, storage_key: str) -> bytes:
        return next(item.content for item in self.saved if item.storage_key == storage_key)

    def delete(self, storage_key: str) -> None:
        self.saved = [item for item in self.saved if item.storage_key != storage_key]

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


class StaticQueryExecutor(CustomReportQueryExecutor):
    def __init__(self, rows: Sequence[Mapping[str, object]] | None = None) -> None:
        self.rows = list(rows or [{"project_no": "Z-2026-0001", "sum_total_budget": "1000"}])
        self.calls = 0

    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        _ = compiled
        self.calls += 1
        return [dict(row) for row in self.rows]


class FailingQueryExecutor(CustomReportQueryExecutor):
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        _ = compiled
        self.calls += 1
        raise RuntimeError("warehouse unavailable")


class RecordingNotificationSender(CustomReportNotificationSender):
    def __init__(self) -> None:
        self.completed: list[tuple[UUID, list[UUID]]] = []
        self.failed: list[tuple[UUID, list[UUID]]] = []

    async def report_completed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None:
        _ = report
        self.completed.append((run_id, list(receiver_ids)))

    async def report_failed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None:
        _ = report
        self.failed.append((run_id, list(receiver_ids)))


@pytest.mark.asyncio
async def test_monthly_scheduled_report_runs_at_owner_local_0900_and_exports_excel() -> None:
    owner = cast(User, UserFactory(role=UserRole.dept_manager, timezone="Asia/Hong_Kong"))
    clock = MutableClock(datetime(2026, 5, 20, 1, 0, tzinfo=UTC))
    service, repository, storage, notifier, _executor = make_service(
        owner=owner,
        now_provider=clock.now,
    )

    report = await service.create_report(
        actor=owner,
        payload=CustomReportDefinitionCreate(
            name="项目月报",
            query_config=ReportQueryConfig.model_validate({
                "dataset": "project_overview",
                "dimensions": ["project_no"],
                "metrics": [
                    {"field": "total_budget", "aggregate": "sum", "alias": "sum_total_budget"}
                ],
            }),
            schedule_frequency=CustomReportScheduleFrequency.monthly,
            schedule_time=time(9, 0),
            schedule_day_of_month=1,
            schedule_timezone="Asia/Hong_Kong",
        ),
    )

    assert report.next_run_at == datetime(2026, 6, 1, 1, 0, tzinfo=UTC)

    clock.current = datetime(2026, 6, 1, 1, 0, tzinfo=UTC)
    result = await service.run_due_scheduled_reports()

    assert result.processed == 1
    assert result.completed == 1
    assert result.failed == 0
    assert report.last_run_at == clock.current
    assert report.next_run_at == datetime(2026, 7, 1, 1, 0, tzinfo=UTC)
    assert len(repository.runs) == 1
    run = repository.runs[0]
    assert run.status == CustomReportRunStatus.completed
    assert run.row_count == 1
    assert run.storage_key == storage.saved[0].storage_key
    assert run.file_format == "zip"
    assert notifier.completed == [(run.id, [owner.id])]

    with ZipFile(BytesIO(storage.saved[0].content)) as archive:
        assert sorted(archive.namelist()) == ["custom_report.csv", "custom_report.xlsx"]
        workbook = load_workbook(BytesIO(archive.read("custom_report.xlsx")))

    assert workbook["summary"]["A1"].value == "report_name"
    assert workbook["summary"]["B1"].value == "项目月报"
    assert workbook["data"]["A1"].value == "project_no"
    assert workbook["data"]["A2"].value == "Z-2026-0001"


@pytest.mark.asyncio
async def test_scheduled_report_retries_three_times_then_marks_failed() -> None:
    owner = cast(User, UserFactory(role=UserRole.dept_manager, timezone="Asia/Shanghai"))
    now = datetime(2026, 6, 2, 1, 0, tzinfo=UTC)
    executor = FailingQueryExecutor()
    service, repository, _storage, notifier, _executor = make_service(
        owner=owner,
        executor=executor,
        now_provider=lambda: now,
    )
    report = make_report(owner, next_run_at=now)
    repository.reports.append(report)

    result = await service.run_due_scheduled_reports(max_attempts=3)

    assert result.processed == 1
    assert result.completed == 0
    assert result.failed == 1
    assert executor.calls == 3
    assert len(repository.runs) == 1
    run = repository.runs[0]
    assert run.status == CustomReportRunStatus.failed
    assert run.error_message == "warehouse unavailable"
    assert report.last_run_at == now
    assert report.next_run_at == datetime(2026, 6, 3, 1, 0, tzinfo=UTC)
    assert notifier.failed == [(run.id, [owner.id])]


def test_celery_beat_schedules_custom_report_scan_every_minute() -> None:
    from app.tasks.celery_app import create_celery_app
    from app.tasks.task_names import CUSTOM_REPORT_SCHEDULE_SCAN_TASK_NAME

    celery_app = create_celery_app()

    schedule = celery_app.conf.beat_schedule["custom-report-schedule-scan-every-minute"]
    assert schedule["task"] == CUSTOM_REPORT_SCHEDULE_SCAN_TASK_NAME
    assert schedule["schedule"] == 60.0


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


def make_service(
    *,
    owner: User,
    executor: CustomReportQueryExecutor | None = None,
    now_provider: Callable[[], datetime],
) -> tuple[
    CustomReportService,
    InMemoryCustomReportRepository,
    RecordingStorage,
    RecordingNotificationSender,
    CustomReportQueryExecutor,
]:
    query_executor = executor or StaticQueryExecutor()
    repository = InMemoryCustomReportRepository(users=[owner])
    storage = RecordingStorage()
    notifier = RecordingNotificationSender()
    service = CustomReportService(
        repository=repository,
        query_executor=query_executor,
        storage=storage,
        notification_sender=notifier,
        now_provider=now_provider,
    )
    return service, repository, storage, notifier, query_executor


def make_report(owner: User, *, next_run_at: datetime) -> CustomReportDefinition:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    return CustomReportDefinition(
        id=uuid4(),
        name="失败日报",
        description=None,
        owner_id=owner.id,
        owner_dept_id=owner.dept_id,
        dataset="project_overview",
        query_config={"dataset": "project_overview", "dimensions": ["project_no"]},
        chart_type="table",
        share_scope=CustomReportShareScope.private,
        schedule_frequency=CustomReportScheduleFrequency.daily,
        schedule_time=time(9, 0),
        schedule_day_of_week=None,
        schedule_day_of_month=None,
        schedule_timezone="Asia/Shanghai",
        last_run_at=None,
        next_run_at=next_run_at,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
