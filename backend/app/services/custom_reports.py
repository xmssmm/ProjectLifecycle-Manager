from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.models.custom_reports import CustomReportDefinition, CustomReportShareScope
from app.models.users import User, UserRole
from app.schemas.custom_reports import (
    CustomReportDefinitionCreate,
    CustomReportDefinitionRead,
    CustomReportPreviewRead,
    ReportDatasetFieldRead,
    ReportDatasetRead,
    ReportQueryConfig,
)
from app.services.audit import AuditContext, AuditLogEntry, AuditLogWriter
from app.services.report_datasets import ReportDatasetRegistry, default_report_dataset_registry
from app.services.report_query_compiler import (
    CompiledReportColumn,
    CompiledReportQuery,
    ReportQueryCompiler,
)

CREATE_REPORT_ROLES = frozenset({UserRole.admin, UserRole.dept_manager})


class CustomReportQueryExecutor(Protocol):
    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]: ...


class SqlAlchemyCustomReportQueryExecutor:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        result = await self._session.execute(compiled.statement, compiled.bound_parameters)
        return [dict(row) for row in result.mappings().all()]


class CustomReportRepository(Protocol):
    async def list_reports(self) -> list[CustomReportDefinition]: ...

    async def get_report(self, report_id: UUID) -> CustomReportDefinition | None: ...

    async def add_report(self, report: CustomReportDefinition) -> CustomReportDefinition: ...

    async def save_report(self, report: CustomReportDefinition) -> CustomReportDefinition: ...


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

    async def get_report(self, report_id: UUID) -> CustomReportDefinition | None:
        report = await self._session.get(CustomReportDefinition, report_id)
        if report is None or not report.is_active:
            return None
        return report

    async def add_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        self._session.add(report)
        await self._session.commit()
        await self._session.refresh(report)
        return report

    async def save_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        await self._session.commit()
        await self._session.refresh(report)
        return report


class InMemoryCustomReportRepository:
    def __init__(
        self,
        reports: Sequence[CustomReportDefinition] | None = None,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.reports = list(reports or [])
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

    async def add_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        report.created_at = report.created_at or self._now_provider()
        report.updated_at = report.updated_at or report.created_at
        self.reports.append(report)
        return report

    async def save_report(self, report: CustomReportDefinition) -> CustomReportDefinition:
        report.updated_at = self._now_provider()
        return report


class CustomReportService:
    def __init__(
        self,
        *,
        repository: CustomReportRepository,
        query_executor: CustomReportQueryExecutor,
        registry: ReportDatasetRegistry | None = None,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._query_executor = query_executor
        self._registry = registry or default_report_dataset_registry()
        self._compiler = ReportQueryCompiler(registry=self._registry)
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
            schedule_frequency=None,
            schedule_time=None,
            schedule_day_of_week=None,
            schedule_day_of_month=None,
            schedule_timezone=None,
            last_run_at=None,
            next_run_at=None,
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
        ).model_dump(mode="json")

    async def _get_existing_report(self, report_id: UUID) -> CustomReportDefinition:
        report = await self._repository.get_report(report_id)
        if report is None:
            raise ResourceNotFoundError("自定义报表不存在")
        return report

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
