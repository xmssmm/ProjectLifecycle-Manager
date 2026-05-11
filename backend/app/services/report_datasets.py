from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import case, literal
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from app.core.exceptions import ValidationFailedError
from app.models.documents import Document
from app.models.main_projects import MainProject
from app.models.payments import Payment
from app.models.sub_projects import SubProject
from app.models.tasks import Task, TaskStatus
from app.schemas.custom_reports import (
    DatasetAggregate,
    DatasetFieldType,
    DatasetFilterOperator,
)

__all__ = [
    "DatasetAggregate",
    "DatasetFilterOperator",
    "ReportDataset",
    "ReportDatasetField",
    "ReportDatasetRegistry",
    "default_report_dataset_registry",
]


@dataclass(frozen=True)
class ReportDatasetField:
    key: str
    label: str
    type: DatasetFieldType
    expression: ColumnElement[Any]
    filter_ops: frozenset[DatasetFilterOperator] = frozenset()
    aggregates: frozenset[DatasetAggregate] = frozenset()


@dataclass(frozen=True)
class ReportDataset:
    key: str
    label: str
    description: str
    default_scope: str
    from_clause: FromClause
    fields: Mapping[str, ReportDatasetField]
    default_predicates: tuple[ColumnElement[bool], ...] = ()
    scope_sub_project_id: ColumnElement[Any] | None = None
    scope_main_project_id: ColumnElement[Any] | None = None
    scope_manager_id: ColumnElement[Any] | None = None

    def require_field(self, key: str) -> ReportDatasetField:
        field = self.fields.get(key)
        if field is None:
            raise ValidationFailedError("未注册报表字段", data={"field": key})
        return field

    def require_metric(
        self,
        key: str,
        aggregate: DatasetAggregate,
    ) -> ReportDatasetField:
        field = self.require_field(key)
        if aggregate not in field.aggregates:
            raise ValidationFailedError(
                "字段不支持该聚合方式",
                data={"field": key, "aggregate": aggregate.value},
            )
        return field

    def require_filter(
        self,
        key: str,
        operator: DatasetFilterOperator,
    ) -> ReportDatasetField:
        field = self.require_field(key)
        if operator not in field.filter_ops:
            raise ValidationFailedError(
                "字段不支持该筛选操作",
                data={"field": key, "operator": operator.value},
            )
        return field


class ReportDatasetRegistry:
    def __init__(self, datasets: Iterable[ReportDataset]) -> None:
        self._datasets = {dataset.key: dataset for dataset in datasets}

    def keys(self) -> list[str]:
        return sorted(self._datasets)

    def require_dataset(self, key: str) -> ReportDataset:
        dataset = self._datasets.get(key)
        if dataset is None:
            raise ValidationFailedError("未注册报表数据集", data={"dataset": key})
        return dataset


TEXT_FILTERS = frozenset(
    {
        DatasetFilterOperator.eq,
        DatasetFilterOperator.ne,
        DatasetFilterOperator.in_,
        DatasetFilterOperator.not_in,
        DatasetFilterOperator.contains,
        DatasetFilterOperator.starts_with,
        DatasetFilterOperator.is_null,
        DatasetFilterOperator.is_not_null,
    },
)
ENUM_FILTERS = frozenset(
    {
        DatasetFilterOperator.eq,
        DatasetFilterOperator.ne,
        DatasetFilterOperator.in_,
        DatasetFilterOperator.not_in,
    },
)
ID_FILTERS = frozenset(
    {
        DatasetFilterOperator.eq,
        DatasetFilterOperator.ne,
        DatasetFilterOperator.in_,
        DatasetFilterOperator.not_in,
        DatasetFilterOperator.is_null,
        DatasetFilterOperator.is_not_null,
    },
)
NUMBER_FILTERS = frozenset(
    {
        DatasetFilterOperator.eq,
        DatasetFilterOperator.ne,
        DatasetFilterOperator.gt,
        DatasetFilterOperator.gte,
        DatasetFilterOperator.lt,
        DatasetFilterOperator.lte,
        DatasetFilterOperator.between,
        DatasetFilterOperator.is_null,
        DatasetFilterOperator.is_not_null,
    },
)
DATE_FILTERS = frozenset(
    {
        DatasetFilterOperator.eq,
        DatasetFilterOperator.ne,
        DatasetFilterOperator.gt,
        DatasetFilterOperator.gte,
        DatasetFilterOperator.lt,
        DatasetFilterOperator.lte,
        DatasetFilterOperator.between,
        DatasetFilterOperator.is_null,
        DatasetFilterOperator.is_not_null,
    },
)
COUNT_AGGREGATES = frozenset({DatasetAggregate.count, DatasetAggregate.count_distinct})
NUMBER_AGGREGATES = frozenset(
    {
        DatasetAggregate.count,
        DatasetAggregate.count_distinct,
        DatasetAggregate.sum,
        DatasetAggregate.avg,
        DatasetAggregate.min,
        DatasetAggregate.max,
    },
)


def _field(
    key: str,
    label: str,
    field_type: DatasetFieldType,
    expression: ColumnElement[Any],
    *,
    filter_ops: frozenset[DatasetFilterOperator] = frozenset(),
    aggregates: frozenset[DatasetAggregate] = frozenset(),
) -> ReportDatasetField:
    return ReportDatasetField(
        key=key,
        label=label,
        type=field_type,
        expression=expression,
        filter_ops=filter_ops,
        aggregates=aggregates,
    )


def default_report_dataset_registry() -> ReportDatasetRegistry:
    main = MainProject.__table__
    sub = SubProject.__table__
    payments = Payment.__table__
    tasks = Task.__table__
    documents = Document.__table__

    project_from = main
    sub_join_main = sub.join(main, sub.c.main_project_id == main.c.id)
    payment_from = payments.join(sub, payments.c.sub_project_id == sub.c.id).join(
        main,
        sub.c.main_project_id == main.c.id,
    )
    task_from = tasks.join(sub, tasks.c.sub_project_id == sub.c.id).join(
        main,
        sub.c.main_project_id == main.c.id,
    )
    document_from = documents.join(sub, documents.c.sub_project_id == sub.c.id).join(
        main,
        sub.c.main_project_id == main.c.id,
    )
    risk_score = case(
        (sub.c.spent_amount > sub.c.budget, literal(70)),
        else_=literal(10),
    )
    risk_level = case(
        (sub.c.spent_amount > sub.c.budget, literal("high")),
        else_=literal("low"),
    )

    return ReportDatasetRegistry(
        [
            ReportDataset(
                key="project_overview",
                label="项目概览",
                description="主项目预算、状态和基础信息。",
                default_scope="project",
                from_clause=project_from,
                scope_main_project_id=main.c.id,
                fields={
                    "id": _field(
                        "id",
                        "主项目ID",
                        DatasetFieldType.uuid,
                        main.c.id,
                        aggregates=COUNT_AGGREGATES,
                    ),
                    "project_no": _field(
                        "project_no",
                        "项目编号",
                        DatasetFieldType.string,
                        main.c.project_no,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "name": _field(
                        "name",
                        "项目名称",
                        DatasetFieldType.string,
                        main.c.name,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "dept_id": _field(
                        "dept_id",
                        "部门ID",
                        DatasetFieldType.uuid,
                        main.c.dept_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "status": _field(
                        "status",
                        "状态",
                        DatasetFieldType.enum,
                        main.c.status,
                        filter_ops=ENUM_FILTERS,
                    ),
                    "total_budget": _field(
                        "total_budget",
                        "总预算",
                        DatasetFieldType.number,
                        main.c.total_budget,
                        filter_ops=NUMBER_FILTERS,
                        aggregates=NUMBER_AGGREGATES,
                    ),
                    "spent_amount": _field(
                        "spent_amount",
                        "已用金额",
                        DatasetFieldType.number,
                        main.c.spent_amount,
                        filter_ops=NUMBER_FILTERS,
                        aggregates=NUMBER_AGGREGATES,
                    ),
                    "created_at": _field(
                        "created_at",
                        "创建时间",
                        DatasetFieldType.datetime,
                        main.c.created_at,
                        filter_ops=DATE_FILTERS,
                    ),
                    "project_type_id": _field(
                        "project_type_id",
                        "项目类型ID",
                        DatasetFieldType.uuid,
                        main.c.project_type_id,
                        filter_ops=ID_FILTERS,
                    ),
                },
            ),
            ReportDataset(
                key="task_overdue",
                label="任务逾期",
                description="逾期任务、所属子项目和负责人范围。",
                default_scope="sub_project",
                from_clause=task_from,
                default_predicates=(tasks.c.status == TaskStatus.overdue.value,),
                scope_sub_project_id=sub.c.id,
                scope_main_project_id=main.c.id,
                scope_manager_id=sub.c.manager_id,
                fields={
                    "id": _field(
                        "id",
                        "任务ID",
                        DatasetFieldType.uuid,
                        tasks.c.id,
                        aggregates=COUNT_AGGREGATES,
                    ),
                    "task_no": _field(
                        "task_no",
                        "任务编号",
                        DatasetFieldType.string,
                        tasks.c.task_no,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "name": _field(
                        "name",
                        "任务名称",
                        DatasetFieldType.string,
                        tasks.c.name,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "status": _field(
                        "status",
                        "任务状态",
                        DatasetFieldType.enum,
                        tasks.c.status,
                        filter_ops=ENUM_FILTERS,
                    ),
                    "plan_end_date": _field(
                        "plan_end_date",
                        "计划完成日期",
                        DatasetFieldType.date,
                        tasks.c.plan_end_date,
                        filter_ops=DATE_FILTERS,
                    ),
                    "sub_project_id": _field(
                        "sub_project_id",
                        "子项目ID",
                        DatasetFieldType.uuid,
                        tasks.c.sub_project_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "manager_id": _field(
                        "manager_id",
                        "负责人ID",
                        DatasetFieldType.uuid,
                        sub.c.manager_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "dept_id": _field(
                        "dept_id",
                        "部门ID",
                        DatasetFieldType.uuid,
                        sub.c.dept_id,
                        filter_ops=ID_FILTERS,
                    ),
                },
            ),
            ReportDataset(
                key="payment_execution",
                label="付款执行",
                description="付款流水、金额、日期和项目维度。",
                default_scope="sub_project",
                from_clause=payment_from,
                scope_sub_project_id=sub.c.id,
                scope_main_project_id=main.c.id,
                scope_manager_id=sub.c.manager_id,
                fields={
                    "id": _field(
                        "id",
                        "付款ID",
                        DatasetFieldType.uuid,
                        payments.c.id,
                        aggregates=COUNT_AGGREGATES,
                    ),
                    "payment_no": _field(
                        "payment_no",
                        "付款编号",
                        DatasetFieldType.string,
                        payments.c.payment_no,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "payment_date": _field(
                        "payment_date",
                        "付款日期",
                        DatasetFieldType.date,
                        payments.c.payment_date,
                        filter_ops=DATE_FILTERS,
                    ),
                    "payment_type": _field(
                        "payment_type",
                        "付款类型",
                        DatasetFieldType.enum,
                        payments.c.payment_type,
                        filter_ops=ENUM_FILTERS,
                    ),
                    "amount": _field(
                        "amount",
                        "付款金额",
                        DatasetFieldType.number,
                        payments.c.amount,
                        filter_ops=NUMBER_FILTERS,
                        aggregates=NUMBER_AGGREGATES,
                    ),
                    "sub_project_id": _field(
                        "sub_project_id",
                        "子项目ID",
                        DatasetFieldType.uuid,
                        payments.c.sub_project_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "manager_id": _field(
                        "manager_id",
                        "负责人ID",
                        DatasetFieldType.uuid,
                        sub.c.manager_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "dept_id": _field(
                        "dept_id",
                        "部门ID",
                        DatasetFieldType.uuid,
                        sub.c.dept_id,
                        filter_ops=ID_FILTERS,
                    ),
                },
            ),
            ReportDataset(
                key="document_upload",
                label="文档上传",
                description="文档类型、上传人、文件大小和扫描状态。",
                default_scope="sub_project",
                from_clause=document_from,
                scope_sub_project_id=sub.c.id,
                scope_main_project_id=main.c.id,
                scope_manager_id=sub.c.manager_id,
                fields={
                    "id": _field(
                        "id",
                        "文档ID",
                        DatasetFieldType.uuid,
                        documents.c.id,
                        aggregates=COUNT_AGGREGATES,
                    ),
                    "doc_type": _field(
                        "doc_type",
                        "文档类型",
                        DatasetFieldType.string,
                        documents.c.doc_type,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "file_size": _field(
                        "file_size",
                        "文件大小",
                        DatasetFieldType.number,
                        documents.c.file_size,
                        filter_ops=NUMBER_FILTERS,
                        aggregates=NUMBER_AGGREGATES,
                    ),
                    "scan_status": _field(
                        "scan_status",
                        "扫描状态",
                        DatasetFieldType.enum,
                        documents.c.scan_status,
                        filter_ops=ENUM_FILTERS,
                    ),
                    "created_at": _field(
                        "created_at",
                        "上传时间",
                        DatasetFieldType.datetime,
                        documents.c.created_at,
                        filter_ops=DATE_FILTERS,
                    ),
                    "uploader_id": _field(
                        "uploader_id",
                        "上传人ID",
                        DatasetFieldType.uuid,
                        documents.c.uploader_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "sub_project_id": _field(
                        "sub_project_id",
                        "子项目ID",
                        DatasetFieldType.uuid,
                        documents.c.sub_project_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "manager_id": _field(
                        "manager_id",
                        "负责人ID",
                        DatasetFieldType.uuid,
                        sub.c.manager_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "dept_id": _field(
                        "dept_id",
                        "部门ID",
                        DatasetFieldType.uuid,
                        sub.c.dept_id,
                        filter_ops=ID_FILTERS,
                    ),
                },
            ),
            ReportDataset(
                key="risk_score",
                label="风险评分",
                description="规则风险评分占位数据集，后续接入 AI 解释摘要。",
                default_scope="sub_project",
                from_clause=sub_join_main,
                scope_sub_project_id=sub.c.id,
                scope_main_project_id=main.c.id,
                scope_manager_id=sub.c.manager_id,
                fields={
                    "sub_project_id": _field(
                        "sub_project_id",
                        "子项目ID",
                        DatasetFieldType.uuid,
                        sub.c.id,
                        filter_ops=ID_FILTERS,
                        aggregates=COUNT_AGGREGATES,
                    ),
                    "project_no": _field(
                        "project_no",
                        "子项目编号",
                        DatasetFieldType.string,
                        sub.c.project_no,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "name": _field(
                        "name",
                        "子项目名称",
                        DatasetFieldType.string,
                        sub.c.name,
                        filter_ops=TEXT_FILTERS,
                    ),
                    "manager_id": _field(
                        "manager_id",
                        "负责人ID",
                        DatasetFieldType.uuid,
                        sub.c.manager_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "dept_id": _field(
                        "dept_id",
                        "部门ID",
                        DatasetFieldType.uuid,
                        sub.c.dept_id,
                        filter_ops=ID_FILTERS,
                    ),
                    "risk_score": _field(
                        "risk_score",
                        "风险分",
                        DatasetFieldType.number,
                        risk_score,
                        filter_ops=NUMBER_FILTERS,
                        aggregates=NUMBER_AGGREGATES,
                    ),
                    "risk_level": _field(
                        "risk_level",
                        "风险等级",
                        DatasetFieldType.enum,
                        risk_level,
                        filter_ops=ENUM_FILTERS,
                    ),
                },
            ),
        ],
    )
