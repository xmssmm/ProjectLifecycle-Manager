from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.custom_reports import ReportDatasetFieldRead, ReportQueryConfig


class AnalyticsQaQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class AnalyticsQaChartSuggestionRead(BaseModel):
    type: str
    x_field: str | None = None
    y_field: str | None = None


class AnalyticsQaAnswerRead(BaseModel):
    question: str
    answer: str
    source: Literal["ai", "rules"]
    query_config: ReportQueryConfig
    columns: list[ReportDatasetFieldRead]
    rows: list[dict[str, Any]]
    row_count: int
    chart: AnalyticsQaChartSuggestionRead
