from __future__ import annotations

import enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.custom_reports import CustomReportShareScope


class DatasetFieldType(enum.StrEnum):
    uuid = "uuid"
    string = "string"
    number = "number"
    date = "date"
    datetime = "datetime"
    enum = "enum"
    boolean = "boolean"


class DatasetFilterOperator(enum.StrEnum):
    eq = "eq"
    ne = "ne"
    in_ = "in"
    not_in = "not_in"
    contains = "contains"
    starts_with = "starts_with"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    between = "between"
    is_null = "is_null"
    is_not_null = "is_not_null"


class DatasetAggregate(enum.Enum):
    count = "count"
    count_distinct = "count_distinct"
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"


class SortDirection(enum.StrEnum):
    asc = "asc"
    desc = "desc"


class ReportMetricConfig(BaseModel):
    field: str
    aggregate: DatasetAggregate
    alias: str | None = Field(default=None, min_length=1, max_length=64)


class ReportFilterConfig(BaseModel):
    field: str
    op: DatasetFilterOperator
    value: Any = None


class ReportSortConfig(BaseModel):
    field: str
    direction: SortDirection = SortDirection.asc


class ReportQueryConfig(BaseModel):
    dataset: str
    dimensions: list[str] = Field(default_factory=list, max_length=20)
    metrics: list[ReportMetricConfig] = Field(default_factory=list, max_length=20)
    filters: list[ReportFilterConfig] = Field(default_factory=list, max_length=50)
    sort: list[ReportSortConfig] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=100, ge=1, le=1000)


class ReportDatasetFieldRead(BaseModel):
    key: str
    label: str
    type: DatasetFieldType
    filter_ops: list[DatasetFilterOperator]
    aggregates: list[DatasetAggregate]


class ReportDatasetRead(BaseModel):
    key: str
    label: str
    description: str
    default_scope: str
    fields: list[ReportDatasetFieldRead]


class CustomReportDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    query_config: ReportQueryConfig
    chart_type: str = Field(default="table", max_length=32)
    share_scope: CustomReportShareScope = CustomReportShareScope.private


class CustomReportPreviewRead(BaseModel):
    columns: list[ReportDatasetFieldRead]
    rows: list[dict[str, Any]]
    row_count: int
    limit: int


class CustomReportDefinitionRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    dataset: str
    query_config: dict[str, Any]
    chart_type: str
    share_scope: CustomReportShareScope
    owner_id: UUID
    owner_dept_id: UUID | None
    is_active: bool
