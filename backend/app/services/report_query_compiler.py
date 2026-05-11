from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, distinct, exists, func, or_, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import BindParameter, ColumnElement

from app.core.exceptions import ValidationFailedError
from app.models.sub_projects import SubProject, SubProjectMember
from app.models.users import User, UserRole
from app.schemas.custom_reports import (
    DatasetAggregate,
    DatasetFieldType,
    DatasetFilterOperator,
    ReportFilterConfig,
    ReportMetricConfig,
    ReportQueryConfig,
    ReportSortConfig,
    SortDirection,
)
from app.services.report_datasets import ReportDataset, ReportDatasetField, ReportDatasetRegistry

GLOBAL_REPORT_ROLES = frozenset(
    {UserRole.admin, UserRole.dept_manager, UserRole.finance_manager},
)


@dataclass(frozen=True)
class CompiledReportColumn:
    key: str
    label: str
    type: DatasetFieldType
    aggregate: DatasetAggregate | None = None


@dataclass(frozen=True)
class CompiledReportScope:
    mode: str
    actor_id: object | None = None


@dataclass(frozen=True)
class CompiledReportQuery:
    dataset_key: str
    statement: Select[Any]
    columns: list[CompiledReportColumn]
    scope: CompiledReportScope
    limit: int
    bound_parameters: Mapping[str, object]


class ReportQueryCompiler:
    def __init__(self, *, registry: ReportDatasetRegistry) -> None:
        self._registry = registry

    def compile(self, *, actor: User, config: ReportQueryConfig) -> CompiledReportQuery:
        dataset = self._registry.require_dataset(config.dataset)
        if not config.dimensions and not config.metrics:
            raise ValidationFailedError("报表查询至少需要一个维度或指标")

        bound_parameters: dict[str, object] = {}
        selected_expressions: list[ColumnElement[Any]] = []
        selected_columns: list[CompiledReportColumn] = []
        selected_by_key: dict[str, ColumnElement[Any]] = {}
        group_by: list[ColumnElement[Any]] = []

        for key in config.dimensions:
            field = dataset.require_field(key)
            expression = field.expression.label(field.key)
            selected_expressions.append(expression)
            selected_by_key[field.key] = expression
            selected_columns.append(
                CompiledReportColumn(key=field.key, label=field.label, type=field.type),
            )
            group_by.append(field.expression)

        for metric in config.metrics:
            field = dataset.require_metric(metric.field, metric.aggregate)
            alias = metric.alias or f"{metric.aggregate.value}_{field.key}"
            if alias in selected_by_key:
                raise ValidationFailedError("报表字段别名重复", data={"alias": alias})
            expression = self._metric_expression(field, metric).label(alias)
            selected_expressions.append(expression)
            selected_by_key[alias] = expression
            selected_columns.append(
                CompiledReportColumn(
                    key=alias,
                    label=alias,
                    type=DatasetFieldType.number,
                    aggregate=metric.aggregate,
                ),
            )

        predicates = list(dataset.default_predicates)
        for index, item in enumerate(config.filters):
            predicates.append(self._filter_expression(dataset, item, index, bound_parameters))

        scope_predicate, scope = self._scope_predicate(dataset=dataset, actor=actor)
        if scope_predicate is not None:
            predicates.append(scope_predicate)
            bound_parameters["actor_id"] = actor.id

        statement = select(*selected_expressions).select_from(dataset.from_clause)
        if predicates:
            statement = statement.where(*predicates)
        if config.metrics and group_by:
            statement = statement.group_by(*group_by)
        for sort_item in config.sort:
            statement = statement.order_by(
                self._sort_expression(sort_item, selected_by_key, dataset),
            )
        statement = statement.limit(config.limit)

        return CompiledReportQuery(
            dataset_key=dataset.key,
            statement=statement,
            columns=selected_columns,
            scope=scope,
            limit=config.limit,
            bound_parameters=bound_parameters,
        )

    @staticmethod
    def _metric_expression(
        field: ReportDatasetField,
        metric: ReportMetricConfig,
    ) -> ColumnElement[Any]:
        if metric.aggregate == DatasetAggregate.count:
            return func.count(field.expression)
        if metric.aggregate == DatasetAggregate.count_distinct:
            return func.count(distinct(field.expression))
        if metric.aggregate == DatasetAggregate.sum:
            return func.sum(field.expression)
        if metric.aggregate == DatasetAggregate.avg:
            return func.avg(field.expression)
        if metric.aggregate == DatasetAggregate.min:
            return func.min(field.expression)
        if metric.aggregate == DatasetAggregate.max:
            return func.max(field.expression)
        raise ValidationFailedError("不支持的聚合方式", data={"aggregate": metric.aggregate.value})

    @staticmethod
    def _filter_expression(
        dataset: ReportDataset,
        item: ReportFilterConfig,
        index: int,
        bound_parameters: dict[str, object],
    ) -> ColumnElement[bool]:
        field = dataset.require_filter(item.field, item.op)
        parameter_name = f"filter_{index}"
        expression = field.expression

        if item.op == DatasetFilterOperator.is_null:
            return expression.is_(None)
        if item.op == DatasetFilterOperator.is_not_null:
            return expression.is_not(None)
        if item.op in {DatasetFilterOperator.in_, DatasetFilterOperator.not_in}:
            if not isinstance(item.value, list):
                raise ValidationFailedError("in 筛选需要数组值", data={"field": item.field})
            bound_parameters[parameter_name] = item.value
            predicate = expression.in_(bindparam(parameter_name, expanding=True))
            return ~predicate if item.op == DatasetFilterOperator.not_in else predicate
        if item.op == DatasetFilterOperator.between:
            if not isinstance(item.value, list) or len(item.value) != 2:
                raise ValidationFailedError(
                    "between 筛选需要两个边界值", data={"field": item.field}
                )
            low_name = f"{parameter_name}_low"
            high_name = f"{parameter_name}_high"
            bound_parameters[low_name] = item.value[0]
            bound_parameters[high_name] = item.value[1]
            return expression.between(bindparam(low_name), bindparam(high_name))

        if item.op == DatasetFilterOperator.contains:
            bound_parameters[parameter_name] = f"%{item.value}%"
            return expression.ilike(bindparam(parameter_name))
        if item.op == DatasetFilterOperator.starts_with:
            bound_parameters[parameter_name] = f"{item.value}%"
            return expression.ilike(bindparam(parameter_name))

        bound_parameters[parameter_name] = item.value
        parameter: BindParameter[Any] = bindparam(parameter_name)
        if item.op == DatasetFilterOperator.eq:
            return expression == parameter
        if item.op == DatasetFilterOperator.ne:
            return expression != parameter
        if item.op == DatasetFilterOperator.gt:
            return expression > parameter
        if item.op == DatasetFilterOperator.gte:
            return expression >= parameter
        if item.op == DatasetFilterOperator.lt:
            return expression < parameter
        if item.op == DatasetFilterOperator.lte:
            return expression <= parameter
        raise ValidationFailedError("不支持的筛选操作", data={"operator": item.op.value})

    @staticmethod
    def _sort_expression(
        item: ReportSortConfig,
        selected_by_key: Mapping[str, ColumnElement[Any]],
        dataset: ReportDataset,
    ) -> ColumnElement[Any]:
        expression = selected_by_key.get(item.field)
        if expression is None:
            expression = dataset.require_field(item.field).expression
        return expression.desc() if item.direction == SortDirection.desc else expression.asc()

    @staticmethod
    def _scope_predicate(
        *,
        dataset: ReportDataset,
        actor: User,
    ) -> tuple[ColumnElement[bool] | None, CompiledReportScope]:
        if actor.role in GLOBAL_REPORT_ROLES:
            return None, CompiledReportScope(mode="global")

        actor_id: BindParameter[Any] = bindparam("actor_id")
        if dataset.scope_sub_project_id is not None:
            member_exists = exists(
                select(SubProjectMember.id).where(
                    SubProjectMember.sub_project_id == dataset.scope_sub_project_id,
                    SubProjectMember.user_id == actor_id,
                ),
            )
            if dataset.scope_manager_id is None:
                return member_exists, CompiledReportScope(
                    mode="owned_sub_projects",
                    actor_id=actor.id,
                )
            return or_(dataset.scope_manager_id == actor_id, member_exists), CompiledReportScope(
                mode="owned_sub_projects",
                actor_id=actor.id,
            )

        if dataset.scope_main_project_id is not None:
            owned_sub_project_exists = exists(
                select(SubProject.id).where(
                    SubProject.main_project_id == dataset.scope_main_project_id,
                    or_(
                        SubProject.manager_id == actor_id,
                        exists(
                            select(SubProjectMember.id).where(
                                SubProjectMember.sub_project_id == SubProject.id,
                                SubProjectMember.user_id == actor_id,
                            ),
                        ),
                    ),
                ),
            )
            return owned_sub_project_exists, CompiledReportScope(
                mode="owned_sub_projects",
                actor_id=actor.id,
            )

        return None, CompiledReportScope(mode="none")
