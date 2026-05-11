from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailedError
from app.models.users import User
from app.schemas.custom_reports import (
    DatasetAggregate,
    DatasetFilterOperator,
    ReportDatasetFieldRead,
    ReportFilterConfig,
    ReportMetricConfig,
    ReportQueryConfig,
    ReportSortConfig,
    SortDirection,
)
from app.services.ai_providers import (
    AiProviderDisabledError,
    AiProviderError,
    AiProviderService,
    AiSchemaValidationError,
)
from app.services.report_datasets import ReportDatasetRegistry, default_report_dataset_registry
from app.services.report_query_compiler import (
    CompiledReportColumn,
    CompiledReportQuery,
    ReportQueryCompiler,
)

AnalyticsQaSource = Literal["ai", "rules"]


class AnalyticsQaQueryExecutor(Protocol):
    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]: ...


class SqlAlchemyAnalyticsQaQueryExecutor:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, compiled: CompiledReportQuery) -> list[dict[str, object]]:
        result = await self._session.execute(compiled.statement, compiled.bound_parameters)
        return [dict(row) for row in result.mappings().all()]


@dataclass(frozen=True)
class AnalyticsQaChartSuggestion:
    type: str
    x_field: str | None = None
    y_field: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "x_field": self.x_field,
            "y_field": self.y_field,
        }


@dataclass(frozen=True)
class AnalyticsQaAnswer:
    question: str
    answer: str
    source: AnalyticsQaSource
    query_config: ReportQueryConfig
    columns: list[ReportDatasetFieldRead]
    rows: list[dict[str, object]]
    row_count: int
    chart: AnalyticsQaChartSuggestion

    def to_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "chart": self.chart.to_dict(),
            "columns": [column.model_dump(mode="json") for column in self.columns],
            "query_config": self.query_config.model_dump(mode="json"),
            "question": self.question,
            "row_count": self.row_count,
            "rows": self.rows,
            "source": self.source,
        }


@dataclass(frozen=True)
class _AnalyticsQaPlan:
    query_config: ReportQueryConfig
    source: AnalyticsQaSource
    chart: AnalyticsQaChartSuggestion
    answer_template: str | None = None
    answer_builder: Callable[[Sequence[Mapping[str, object]]], str] | None = None


class AnalyticsQaService:
    def __init__(
        self,
        *,
        ai_service: AiProviderService | None = None,
        query_executor: AnalyticsQaQueryExecutor,
        registry: ReportDatasetRegistry | None = None,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._ai_service = ai_service
        self._query_executor = query_executor
        self._registry = registry or default_report_dataset_registry()
        self._compiler = ReportQueryCompiler(registry=self._registry)
        self._now_provider = now_provider

    async def answer_question(self, *, actor: User, question: str) -> AnalyticsQaAnswer:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValidationFailedError("Analytics question is required")

        plan = await self._build_plan(actor=actor, question=cleaned_question)
        compiled = self._compiler.compile(actor=actor, config=plan.query_config)
        rows = await self._query_executor.execute(compiled)
        answer = self._format_answer(plan=plan, rows=rows)
        return AnalyticsQaAnswer(
            answer=answer,
            chart=plan.chart,
            columns=[self._column_read(column) for column in compiled.columns],
            query_config=plan.query_config,
            question=cleaned_question,
            row_count=len(rows),
            rows=rows,
            source=plan.source,
        )

    async def _build_plan(self, *, actor: User, question: str) -> _AnalyticsQaPlan:
        if self._ai_service is not None:
            try:
                return await self._build_ai_plan(actor=actor, question=question)
            except (AiProviderDisabledError, AiProviderError, AiSchemaValidationError):
                pass
        return self._build_rule_plan(actor=actor, question=question)

    async def _build_ai_plan(self, *, actor: User, question: str) -> _AnalyticsQaPlan:
        if self._ai_service is None:
            raise AiProviderDisabledError("AI provider is disabled")
        dataset_keys = self._registry.keys()
        prompt = (
            "Map the analytics question to a controlled custom-report query_config. "
            "Return JSON only. Do not return SQL. Allowed datasets: "
            f"{dataset_keys}. Question: {question}"
        )
        payload = await self._ai_service.complete_json(
            actor_id=actor.id,
            prompt=prompt,
            purpose="analytics_qa",
            schema_name="analytics_query_config",
        )
        query_config = ReportQueryConfig.model_validate(payload["query_config"])
        return _AnalyticsQaPlan(
            answer_template=str(payload.get("answer_template", "{row_count} rows")),
            chart=AnalyticsQaChartSuggestion(
                type=str(payload.get("chart_type", "table")),
                x_field=cast(str | None, payload.get("x_field")),
                y_field=cast(str | None, payload.get("y_field")),
            ),
            query_config=query_config,
            source="ai",
        )

    def _build_rule_plan(self, *, actor: User, question: str) -> _AnalyticsQaPlan:
        normalized = question.casefold()
        if "项目数" in question or "项目数量" in question or "project count" in normalized:
            return self._department_project_count_plan(actor)
        if "平均周期" in question or "avg cycle" in normalized:
            return self._average_cycle_plan(actor)
        if "逾期" in question and ("最多" in question or "top" in normalized):
            return self._top_overdue_task_plan()
        raise ValidationFailedError("Unsupported analytics question")

    def _department_project_count_plan(self, actor: User) -> _AnalyticsQaPlan:
        return _AnalyticsQaPlan(
            answer_builder=_format_project_count_answer,
            chart=AnalyticsQaChartSuggestion(type="stat", y_field="project_count"),
            query_config=ReportQueryConfig(
                dataset="project_overview",
                filters=self._current_year_department_filters(actor),
                limit=1,
                metrics=[
                    ReportMetricConfig(
                        aggregate=DatasetAggregate.count,
                        alias="project_count",
                        field="id",
                    ),
                ],
            ),
            source="rules",
        )

    def _average_cycle_plan(self, actor: User) -> _AnalyticsQaPlan:
        return _AnalyticsQaPlan(
            answer_builder=_format_average_cycle_answer,
            chart=AnalyticsQaChartSuggestion(type="stat", y_field="average_cycle_days"),
            query_config=ReportQueryConfig(
                dataset="project_overview",
                filters=self._current_year_department_filters(actor),
                limit=1,
                metrics=[
                    ReportMetricConfig(
                        aggregate=DatasetAggregate.avg,
                        alias="average_cycle_days",
                        field="cycle_days",
                    ),
                ],
            ),
            source="rules",
        )

    @staticmethod
    def _top_overdue_task_plan() -> _AnalyticsQaPlan:
        return _AnalyticsQaPlan(
            answer_builder=_format_top_overdue_answer,
            chart=AnalyticsQaChartSuggestion(
                type="bar",
                x_field="sub_project_id",
                y_field="overdue_task_count",
            ),
            query_config=ReportQueryConfig(
                dataset="task_overdue",
                dimensions=["sub_project_id"],
                limit=5,
                metrics=[
                    ReportMetricConfig(
                        aggregate=DatasetAggregate.count,
                        alias="overdue_task_count",
                        field="id",
                    ),
                ],
                sort=[
                    ReportSortConfig(
                        direction=SortDirection.desc,
                        field="overdue_task_count",
                    ),
                ],
            ),
            source="rules",
        )

    def _current_year_department_filters(self, actor: User) -> list[ReportFilterConfig]:
        now = self._current_utc()
        start = datetime(now.year, 1, 1, tzinfo=UTC)
        end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
        filters = [
            ReportFilterConfig(
                field="created_at",
                op=DatasetFilterOperator.gte,
                value=start,
            ),
            ReportFilterConfig(
                field="created_at",
                op=DatasetFilterOperator.lt,
                value=end,
            ),
        ]
        if actor.dept_id is not None:
            filters.append(
                ReportFilterConfig(
                    field="dept_id",
                    op=DatasetFilterOperator.eq,
                    value=actor.dept_id,
                ),
            )
        return filters

    def _current_utc(self) -> datetime:
        now = self._now_provider()
        return now if now.tzinfo is not None else now.replace(tzinfo=UTC)

    @staticmethod
    def _format_answer(
        *,
        plan: _AnalyticsQaPlan,
        rows: Sequence[Mapping[str, object]],
    ) -> str:
        if plan.answer_builder is not None:
            return plan.answer_builder(rows)
        if plan.answer_template is not None:
            first_row = dict(rows[0]) if rows else {}
            values: dict[str, object] = {"row_count": len(rows), **first_row}
            try:
                return plan.answer_template.format(**values)
            except (KeyError, ValueError):
                return f"查询完成，共返回 {len(rows)} 行。"
        return f"查询完成，共返回 {len(rows)} 行。"

    @staticmethod
    def _column_read(column: CompiledReportColumn) -> ReportDatasetFieldRead:
        return ReportDatasetFieldRead(
            aggregates=[column.aggregate] if column.aggregate is not None else [],
            filter_ops=[],
            key=column.key,
            label=column.label,
            type=column.type,
        )


def _format_project_count_answer(rows: Sequence[Mapping[str, object]]) -> str:
    count = _first_numeric(rows, "project_count")
    return f"本部门今年项目数为 {count:.0f} 个。"


def _format_average_cycle_answer(rows: Sequence[Mapping[str, object]]) -> str:
    days = _first_numeric(rows, "average_cycle_days")
    return f"本部门今年项目平均周期为 {days:.2f} 天。"


def _format_top_overdue_answer(rows: Sequence[Mapping[str, object]]) -> str:
    if not rows:
        return "当前权限范围内暂无逾期任务。"
    row = rows[0]
    project = str(row.get("sub_project_id", "-"))
    count = _first_numeric(rows, "overdue_task_count")
    return f"逾期任务最多的项目为 {project}，逾期任务 {count:.0f} 个。"


def _first_numeric(rows: Sequence[Mapping[str, object]], key: str) -> float:
    if not rows:
        return 0
    value = rows[0].get(key, 0)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0
    return 0
