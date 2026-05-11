from __future__ import annotations

import calendar
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Protocol, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, PermissionDeniedError, ResourceNotFoundError
from app.models.custom_reports import (
    CustomReportDefinition,
    CustomReportRun,
    CustomReportRunStatus,
    CustomReportScheduleFrequency,
    CustomReportShareScope,
)
from app.models.users import DEFAULT_USER_TIMEZONE, User, UserRole, UserStatus
from app.schemas.custom_reports import (
    CustomReportDefinitionCreate,
    CustomReportDefinitionRead,
    CustomReportPreviewRead,
    ReportDatasetFieldRead,
    ReportDatasetRead,
    ReportQueryConfig,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter
from app.services.database_exports import TabularExportColumn, TabularExportRenderer
from app.services.notifications import NotificationService
from app.services.report_datasets import ReportDatasetRegistry, default_report_dataset_registry
from app.services.report_query_compiler import (
    CompiledReportColumn,
    CompiledReportQuery,
    ReportQueryCompiler,
)
from app.storage.base import StorageBackend

CREATE_REPORT_ROLES = frozenset({UserRole.admin, UserRole.dept_manager})
CUSTOM_REPORT_COMPLETED_SCENARIO = "custom_report_generated"
CUSTOM_REPORT_FAILED_SCENARIO = "custom_report_failed"


@dataclass(frozen=True)
class CustomReportDownload:
    file_name: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class CustomReportScheduleBatchResult:
    processed: int
    completed: int
    failed: int

    def to_dict(self) -> dict[str, int]:
        return {"processed": self.processed, "completed": self.completed, "failed": self.failed}


class CustomReportQueryExecutor(Protocol):
    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]: ...


class CustomReportNotificationSender(Protocol):
    async def report_completed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None: ...

    async def report_failed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None: ...


class NoopCustomReportNotificationSender:
    async def report_completed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None:
        _ = (report, run_id, receiver_ids)

    async def report_failed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None:
        _ = (report, run_id, receiver_ids)


class NotificationServiceCustomReportSender:
    def __init__(self, notification_service: NotificationService) -> None:
        self._notification_service = notification_service

    async def report_completed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None:
        await self._notification_service.send(
            scenario=CUSTOM_REPORT_COMPLETED_SCENARIO,
            receivers=receiver_ids,
            source_id=run_id,
            payload={"report_id": str(report.id), "report_name": report.name},
        )

    async def report_failed(
        self,
        *,
        report: CustomReportDefinition,
        run_id: UUID,
        receiver_ids: Sequence[UUID],
    ) -> None:
        await self._notification_service.send(
            scenario=CUSTOM_REPORT_FAILED_SCENARIO,
            receivers=receiver_ids,
            source_id=run_id,
            payload={"report_id": str(report.id), "report_name": report.name},
        )


class SqlAlchemyCustomReportQueryExecutor:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        result = await self._session.execute(compiled.statement, compiled.bound_parameters)
        return [dict(row) for row in result.mappings().all()]


class CustomReportRepository(Protocol):
    async def list_reports(self) -> list[CustomReportDefinition]: ...

    async def list_due_scheduled_reports(
        self,
        due_at: datetime,
    ) -> list[CustomReportDefinition]: ...

    async def get_report(self, report_id: UUID) -> CustomReportDefinition | None: ...

    async def get_user(self, user_id: UUID) -> User | None: ...

    async def list_share_receiver_ids(self, report: CustomReportDefinition) -> list[UUID]: ...

    async def add_report(self, report: CustomReportDefinition) -> CustomReportDefinition: ...

    async def save_report(self, report: CustomReportDefinition) -> CustomReportDefinition: ...

    async def add_run(self, run: CustomReportRun) -> CustomReportRun: ...

    async def get_run(self, run_id: UUID) -> CustomReportRun | None: ...

    async def save_run(self, run: CustomReportRun) -> CustomReportRun: ...


class SqlAlchemyCustomReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_reports(self) -> list[CustomReportDefinition]:
        result = await self._session.scalars(
            select(CustomReportDefinition)
            .where(CustomReportDefinition.is_active.is_(True))
            .order_by(CustomReportDefinition.created_at.desc()),
        )
        return list(result.all())

    async def list_due_scheduled_reports(self, due_at: datetime) -> list[CustomReportDefinition]:
        result = await self._session.scalars(
            select(CustomReportDefinition)
            .where(
                CustomReportDefinition.is_active.is_(True),
                CustomReportDefinition.schedule_frequency.is_not(None),
                CustomReportDefinition.next_run_at.is_not(None),
                CustomReportDefinition.next_run_at <= due_at,
            )
            .order_by(CustomReportDefinition.next_run_at),
        )
        return list(result.all())

    async def get_report(self, report_id: UUID) -> CustomReportDefinition | None:
        report = await self._session.get(CustomReportDefinition, report_id)
        if report is None or not report.is_active:
            return None
        return report

    async def get_user(self, user_id: UUID) -> User | None:
        user = await self._session.get(User, user_id)
        return user if isinstance(user, User) and user.status != UserStatus.disabled else None

    async def list_share_receiver_ids(self, report: CustomReportDefinition) -> list[UUID]:
        conditions = [User.status != UserStatus.disabled]
        if report.share_scope == CustomReportShareScope.private:
            conditions.append(User.id == report.owner_id)
        elif report.share_scope == CustomReportShareScope.department:
            conditions.append(User.dept_id == report.owner_dept_id)
        result = await self._session.scalars(select(User.id).where(*conditions).order_by(User.id))
        receiver_ids = list(result.all())
        if report.owner_id not in receiver_ids:
            receiver_ids.insert(0, report.owner_id)
        return receiver_ids

    async def add_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        self._session.add(report)
        await self._session.commit()
        await self._session.refresh(report)
        return report

    async def save_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        await self._session.commit()
        await self._session.refresh(report)
        return report

    async def add_run(self, run: CustomReportRun) -> CustomReportRun:
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def get_run(self, run_id: UUID) -> CustomReportRun | None:
        return await self._session.get(CustomReportRun, run_id)

    async def save_run(self, run: CustomReportRun) -> CustomReportRun:
        await self._session.commit()
        await self._session.refresh(run)
        return run


class InMemoryCustomReportRepository:
    def __init__(
        self,
        reports: Sequence[CustomReportDefinition] | None = None,
        runs: Sequence[CustomReportRun] | None = None,
        users: Sequence[User] | None = None,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.reports = list(reports or [])
        self.runs = list(runs or [])
        self.users = list(users or [])
        self._now_provider = now_provider

    async def list_reports(self) -> list[CustomReportDefinition]:
        return sorted(
            [report for report in self.reports if report.is_active],
            key=lambda report: report.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    async def get_report(self, report_id: UUID) -> CustomReportDefinition | None:
        return next(
            (report for report in self.reports if report.id == report_id and report.is_active),
            None,
        )

    async def list_due_scheduled_reports(self, due_at: datetime) -> list[CustomReportDefinition]:
        return sorted(
            [
                report
                for report in self.reports
                if report.is_active
                and report.schedule_frequency is not None
                and report.next_run_at is not None
                and report.next_run_at <= due_at
            ],
            key=lambda report: report.next_run_at or datetime.max.replace(tzinfo=UTC),
        )

    async def get_user(self, user_id: UUID) -> User | None:
        return next(
            (
                user
                for user in self.users
                if user.id == user_id and user.status != UserStatus.disabled
            ),
            None,
        )

    async def list_share_receiver_ids(self, report: CustomReportDefinition) -> list[UUID]:
        if report.share_scope == CustomReportShareScope.global_:
            receiver_ids = [user.id for user in self.users if user.status != UserStatus.disabled]
        elif report.share_scope == CustomReportShareScope.department:
            receiver_ids = [
                user.id
                for user in self.users
                if user.status != UserStatus.disabled and user.dept_id == report.owner_dept_id
            ]
        else:
            receiver_ids = [report.owner_id]
        if report.owner_id not in receiver_ids:
            receiver_ids.insert(0, report.owner_id)
        return receiver_ids

    async def add_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        report.created_at = report.created_at or self._now_provider()
        report.updated_at = report.updated_at or report.created_at
        self.reports.append(report)
        return report

    async def save_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        report.updated_at = self._now_provider()
        return report

    async def add_run(self, run: CustomReportRun) -> CustomReportRun:
        run.created_at = run.created_at or self._now_provider()
        run.updated_at = run.updated_at or run.created_at
        self.runs.append(run)
        return run

    async def get_run(self, run_id: UUID) -> CustomReportRun | None:
        return next((run for run in self.runs if run.id == run_id), None)

    async def save_run(self, run: CustomReportRun) -> CustomReportRun:
        run.updated_at = self._now_provider()
        return run


class CustomReportService:
    def __init__(
        self,
        *,
        repository: CustomReportRepository,
        query_executor: CustomReportQueryExecutor,
        registry: ReportDatasetRegistry | None = None,
        storage: StorageBackend | None = None,
        notification_sender: CustomReportNotificationSender | None = None,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._query_executor = query_executor
        self._registry = registry or default_report_dataset_registry()
        self._compiler = ReportQueryCompiler(registry=self._registry)
        self._storage = storage
        self._notification_sender = notification_sender or NoopCustomReportNotificationSender()
        self._now_provider = now_provider

    def list_datasets(self, *, actor: User) -> list[ReportDatasetRead]:
        _ = actor
        return [
            ReportDatasetRead(
                key=dataset.key,
                label=dataset.label,
                description=dataset.description,
                default_scope=dataset.default_scope,
                fields=[
                    ReportDatasetFieldRead(
                        key=field.key,
                        label=field.label,
                        type=field.type,
                        filter_ops=sorted(field.filter_ops, key=lambda item: item.value),
                        aggregates=sorted(field.aggregates, key=lambda item: item.value),
                    )
                    for field in dataset.fields.values()
                ],
            )
            for dataset in [self._registry.require_dataset(key) for key in self._registry.keys()]
        ]

    async def preview_query(
        self,
        *,
        actor: User,
        query_config: ReportQueryConfig,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> CustomReportPreviewRead:
        compiled = self._compiler.compile(actor=actor, config=query_config)
        rows = await self._query_executor.execute(compiled)
        preview = CustomReportPreviewRead(
            columns=[self._preview_column(column) for column in compiled.columns],
            rows=rows,
            row_count=len(rows),
            limit=compiled.limit,
        )
        self._record_audit(
            action="custom_report.preview",
            actor=actor,
            target_id=query_config.dataset,
            after_state={"row_count": len(rows), "dataset": query_config.dataset},
            audit_writer=audit_writer,
            audit_context=audit_context,
        )
        return preview

    async def preview_report(
        self,
        *,
        actor: User,
        report_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> CustomReportPreviewRead:
        report = await self._get_visible_report(actor=actor, report_id=report_id)
        return await self.preview_query(
            actor=actor,
            query_config=ReportQueryConfig.model_validate(report.query_config),
            audit_writer=audit_writer,
            audit_context=audit_context,
        )

    async def create_report(
        self,
        *,
        actor: User,
        payload: CustomReportDefinitionCreate,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> CustomReportDefinition:
        if actor.role not in CREATE_REPORT_ROLES:
            raise PermissionDeniedError("只有管理员和部门负责人可以保存自定义报表")
        self._compiler.compile(actor=actor, config=payload.query_config)
        now = self._now_provider()
        report = CustomReportDefinition(
            id=uuid4(),
            name=payload.name,
            description=payload.description,
            owner_id=actor.id,
            owner_dept_id=actor.dept_id,
            dataset=payload.query_config.dataset,
            query_config=payload.query_config.model_dump(mode="json"),
            chart_type=payload.chart_type,
            share_scope=payload.share_scope,
            schedule_frequency=payload.schedule_frequency,
            schedule_time=payload.schedule_time,
            schedule_day_of_week=payload.schedule_day_of_week,
            schedule_day_of_month=payload.schedule_day_of_month,
            schedule_timezone=payload.schedule_timezone,
            last_run_at=None,
            next_run_at=self._next_run_at_from_payload(payload=payload, from_utc=now),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        report = await self._repository.add_report(report)
        self._record_audit(
            action="custom_report.create",
            actor=actor,
            target_id=str(report.id),
            after_state=self.serialize_report(report),
            audit_writer=audit_writer,
            audit_context=audit_context,
        )
        return report

    async def list_reports(self, *, actor: User) -> list[CustomReportDefinition]:
        reports = await self._repository.list_reports()
        return [report for report in reports if self._can_view(actor, report)]

    async def delete_report(
        self,
        *,
        actor: User,
        report_id: UUID,
        audit_writer: AuditLogWriter | None = None,
        audit_context: AuditContext | None = None,
    ) -> CustomReportDefinition:
        report = await self._get_existing_report(report_id)
        if actor.role != UserRole.admin and report.owner_id != actor.id:
            raise PermissionDeniedError()
        before_state = self.serialize_report(report)
        report.is_active = False
        report = await self._repository.save_report(report)
        self._record_audit(
            action="custom_report.delete",
            actor=actor,
            target_id=str(report.id),
            before_state=before_state,
            after_state=self.serialize_report(report),
            audit_writer=audit_writer,
            audit_context=audit_context,
        )
        return report

    async def run_due_scheduled_reports(
        self,
        *,
        max_attempts: int = 3,
    ) -> CustomReportScheduleBatchResult:
        now = self._current_utc()
        reports = await self._repository.list_due_scheduled_reports(now)
        completed = 0
        failed = 0
        for report in reports:
            run = await self.run_scheduled_report(
                report_id=report.id,
                triggered_by_id=report.owner_id,
                max_attempts=max_attempts,
            )
            if run.status == CustomReportRunStatus.completed:
                completed += 1
            else:
                failed += 1
        return CustomReportScheduleBatchResult(
            processed=len(reports),
            completed=completed,
            failed=failed,
        )

    async def run_scheduled_report(
        self,
        *,
        report_id: UUID,
        triggered_by_id: UUID | None = None,
        max_attempts: int = 3,
    ) -> CustomReportRun:
        if self._storage is None:
            raise BusinessException(code=3033, message="Custom report storage is not configured")
        report = await self._get_existing_report(report_id)
        owner = await self._repository.get_user(report.owner_id)
        if owner is None:
            raise ResourceNotFoundError("Custom report owner does not exist")
        now = self._current_utc()
        run = CustomReportRun(
            id=uuid4(),
            report_id=report.id,
            triggered_by_id=triggered_by_id,
            status=CustomReportRunStatus.queued,
            row_count=0,
            storage_key=None,
            file_format=None,
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._repository.add_run(run)
        receivers = await self._repository.list_share_receiver_ids(report)
        attempts = max(1, max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                return await self._execute_scheduled_run(
                    owner=owner,
                    report=report,
                    run=run,
                    receiver_ids=receivers,
                )
            except Exception as exc:
                if attempt < attempts:
                    continue
                return await self._mark_scheduled_run_failed(
                    report=report,
                    run=run,
                    receiver_ids=receivers,
                    error=exc,
                )
        return run

    async def download_run(self, *, actor: User, run_id: UUID) -> CustomReportDownload:
        if self._storage is None:
            raise BusinessException(code=3033, message="Custom report storage is not configured")
        run = await self._get_existing_run(run_id)
        if run.status != CustomReportRunStatus.completed:
            raise BusinessException(
                code=3034,
                message="Custom report export is not ready",
                status_code=409,
                data={"status": run.status.value},
            )
        if run.storage_key is None:
            raise ResourceNotFoundError("Custom report export file does not exist")
        report = await self._get_visible_report(actor=actor, report_id=run.report_id)
        _ = report
        return CustomReportDownload(
            file_name="custom_report.zip",
            content_type="application/zip",
            content=self._storage.read(run.storage_key),
        )

    def serialize_report(self, report: CustomReportDefinition) -> dict[str, object]:
        return CustomReportDefinitionRead(
            id=report.id,
            name=report.name,
            description=report.description,
            dataset=report.dataset,
            query_config=report.query_config,
            chart_type=report.chart_type,
            share_scope=report.share_scope,
            owner_id=report.owner_id,
            owner_dept_id=report.owner_dept_id,
            is_active=report.is_active,
            schedule_frequency=report.schedule_frequency,
            schedule_time=report.schedule_time,
            schedule_day_of_week=report.schedule_day_of_week,
            schedule_day_of_month=report.schedule_day_of_month,
            schedule_timezone=report.schedule_timezone,
            last_run_at=report.last_run_at,
            next_run_at=report.next_run_at,
        ).model_dump(mode="json")

    async def _get_existing_report(self, report_id: UUID) -> CustomReportDefinition:
        report = await self._repository.get_report(report_id)
        if report is None:
            raise ResourceNotFoundError("自定义报表不存在")
        return report

    async def _get_existing_run(self, run_id: UUID) -> CustomReportRun:
        run = await self._repository.get_run(run_id)
        if run is None:
            raise ResourceNotFoundError("Custom report run does not exist")
        return run

    async def _get_visible_report(
        self,
        *,
        actor: User,
        report_id: UUID,
    ) -> CustomReportDefinition:
        report = await self._get_existing_report(report_id)
        if not self._can_view(actor, report):
            raise PermissionDeniedError()
        return report

    @staticmethod
    def _can_view(actor: User, report: CustomReportDefinition) -> bool:
        if actor.role == UserRole.admin or report.owner_id == actor.id:
            return True
        if report.share_scope == CustomReportShareScope.global_:
            return True
        return (
            report.share_scope == CustomReportShareScope.department
            and actor.dept_id is not None
            and actor.dept_id == report.owner_dept_id
        )

    async def _execute_scheduled_run(
        self,
        *,
        owner: User,
        report: CustomReportDefinition,
        run: CustomReportRun,
        receiver_ids: Sequence[UUID],
    ) -> CustomReportRun:
        if self._storage is None:
            raise BusinessException(code=3033, message="Custom report storage is not configured")
        now = self._current_utc()
        run.status = CustomReportRunStatus.running
        run.started_at = run.started_at or now
        run.error_message = None
        run.updated_at = now
        await self._repository.save_run(run)

        compiled = self._compiler.compile(
            actor=owner,
            config=ReportQueryConfig.model_validate(report.query_config),
        )
        rows = await self._query_executor.execute(compiled)
        package = TabularExportRenderer.render_zip(
            columns=[self._export_column(column) for column in compiled.columns],
            rows=rows,
            summary=self._export_summary(report=report, row_count=len(rows)),
        )
        run.storage_key = self._storage.save(
            sub_id="custom-reports",
            phase_id=str(report.id),
            filename="custom_report.zip",
            content=package,
        )
        run.file_format = "zip"
        run.status = CustomReportRunStatus.completed
        run.row_count = len(rows)
        run.finished_at = self._current_utc()
        run.updated_at = run.finished_at
        report.last_run_at = run.finished_at
        report.next_run_at = self._next_run_at_for_report(report=report, from_utc=run.finished_at)
        await self._repository.save_run(run)
        await self._repository.save_report(report)
        await self._notification_sender.report_completed(
            report=report,
            run_id=run.id,
            receiver_ids=receiver_ids,
        )
        return run

    async def _mark_scheduled_run_failed(
        self,
        *,
        report: CustomReportDefinition,
        run: CustomReportRun,
        receiver_ids: Sequence[UUID],
        error: Exception,
    ) -> CustomReportRun:
        now = self._current_utc()
        run.status = CustomReportRunStatus.failed
        run.error_message = str(error)
        run.finished_at = now
        run.updated_at = now
        report.last_run_at = now
        report.next_run_at = self._next_run_at_for_report(report=report, from_utc=now)
        await self._repository.save_run(run)
        await self._repository.save_report(report)
        await self._notification_sender.report_failed(
            report=report,
            run_id=run.id,
            receiver_ids=receiver_ids,
        )
        return run

    def _next_run_at_from_payload(
        self,
        *,
        payload: CustomReportDefinitionCreate,
        from_utc: datetime,
    ) -> datetime | None:
        if payload.schedule_frequency is None:
            return None
        return self._calculate_next_run_at(
            frequency=payload.schedule_frequency,
            schedule_time=payload.schedule_time,
            timezone_name=payload.schedule_timezone,
            from_utc=from_utc,
            day_of_week=payload.schedule_day_of_week,
            day_of_month=payload.schedule_day_of_month,
        )

    def _next_run_at_for_report(
        self,
        *,
        report: CustomReportDefinition,
        from_utc: datetime,
    ) -> datetime | None:
        if report.schedule_frequency is None:
            return None
        return self._calculate_next_run_at(
            frequency=report.schedule_frequency,
            schedule_time=report.schedule_time,
            timezone_name=report.schedule_timezone,
            from_utc=from_utc + timedelta(seconds=1),
            day_of_week=report.schedule_day_of_week,
            day_of_month=report.schedule_day_of_month,
        )

    @staticmethod
    def _calculate_next_run_at(
        *,
        frequency: CustomReportScheduleFrequency,
        schedule_time: object,
        timezone_name: str | None,
        from_utc: datetime,
        day_of_week: int | None,
        day_of_month: int | None,
    ) -> datetime:
        if not hasattr(schedule_time, "hour") or not hasattr(schedule_time, "minute"):
            raise ValueError("schedule_time is required")
        target_time = cast(time, schedule_time)
        current_utc = from_utc if from_utc.tzinfo is not None else from_utc.replace(tzinfo=UTC)
        timezone = CustomReportService._resolve_timezone(timezone_name)
        local_now = current_utc.astimezone(timezone)
        if frequency == CustomReportScheduleFrequency.daily:
            candidate = datetime.combine(local_now.date(), target_time, tzinfo=timezone)
            if candidate <= local_now:
                candidate += timedelta(days=1)
            return candidate.astimezone(UTC)
        if frequency == CustomReportScheduleFrequency.weekly:
            target_weekday = (day_of_week or 1) - 1
            days_until = (target_weekday - local_now.weekday()) % 7
            candidate = datetime.combine(
                local_now.date() + timedelta(days=days_until),
                target_time,
                tzinfo=timezone,
            )
            if candidate <= local_now:
                candidate += timedelta(days=7)
            return candidate.astimezone(UTC)

        target_day = day_of_month or 1
        year = local_now.year
        month = local_now.month
        candidate = CustomReportService._monthly_candidate(
            year=year,
            month=month,
            day=target_day,
            schedule_time=target_time,
            timezone=timezone,
        )
        if candidate <= local_now:
            month += 1
            if month > 12:
                year += 1
                month = 1
            candidate = CustomReportService._monthly_candidate(
                year=year,
                month=month,
                day=target_day,
                schedule_time=target_time,
                timezone=timezone,
            )
        return candidate.astimezone(UTC)

    @staticmethod
    def _monthly_candidate(
        *,
        year: int,
        month: int,
        day: int,
        schedule_time: time,
        timezone: ZoneInfo,
    ) -> datetime:
        resolved_day = min(day, calendar.monthrange(year, month)[1])
        return datetime.combine(
            datetime(year, month, resolved_day).date(),
            schedule_time,
            tzinfo=timezone,
        )

    @staticmethod
    def _resolve_timezone(timezone_name: str | None) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name or DEFAULT_USER_TIMEZONE)
        except ZoneInfoNotFoundError:
            return ZoneInfo(DEFAULT_USER_TIMEZONE)

    def _current_utc(self) -> datetime:
        now = self._now_provider()
        return now if now.tzinfo is not None else now.replace(tzinfo=UTC)

    @staticmethod
    def _export_column(column: CompiledReportColumn) -> TabularExportColumn:
        return TabularExportColumn(key=column.key, label=column.label)

    @staticmethod
    def _export_summary(
        *,
        report: CustomReportDefinition,
        row_count: int,
    ) -> dict[str, object]:
        return {
            "report_name": report.name,
            "dataset": report.dataset,
            "chart_type": report.chart_type,
            "share_scope": report.share_scope.value,
            "row_count": row_count,
            "filters": report.query_config.get("filters", []),
        }

    @staticmethod
    def _preview_column(column: CompiledReportColumn) -> ReportDatasetFieldRead:
        return ReportDatasetFieldRead(
            key=column.key,
            label=column.label,
            type=column.type,
            filter_ops=[],
            aggregates=([column.aggregate] if column.aggregate is not None else []),
        )

    @staticmethod
    def _record_audit(
        *,
        action: str,
        actor: User,
        target_id: str,
        after_state: Mapping[str, object],
        audit_writer: AuditLogWriter | None,
        audit_context: AuditContext | None,
        before_state: Mapping[str, object] | None = None,
    ) -> None:
        if audit_writer is None:
            return
        context = audit_context or AuditContext(actor_id=actor.id)
        audit_writer.enqueue(
            AuditLogEntry(
                actor_id=context.actor_id or actor.id,
                action=action,
                target_type="custom_report",
                target_id=target_id,
                before_state=dict(before_state or {}),
                after_state=dict(after_state),
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                extra={},
                request_id=context.request_id,
            ),
        )
