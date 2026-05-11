from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.exceptions import ValidationFailedError
from app.schemas.custom_reports import ReportQueryConfig


class AiRiskSummary(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    recommendations: list[str] = Field(default_factory=list, max_length=10)


class AiDocumentTypeSuggestion(BaseModel):
    doc_type: str = Field(min_length=1, max_length=64)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=300)


class AiDocumentTypeSuggestions(BaseModel):
    suggestions: list[AiDocumentTypeSuggestion] = Field(default_factory=list, max_length=5)


class AiAnalyticsQueryConfig(BaseModel):
    query_config: ReportQueryConfig
    answer_template: str = Field(min_length=1, max_length=500)
    chart_type: str = Field(default="table", max_length=32)
    x_field: str | None = Field(default=None, max_length=64)
    y_field: str | None = Field(default=None, max_length=64)


AI_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "analytics_query_config": AiAnalyticsQueryConfig,
    "document_type_suggestions": AiDocumentTypeSuggestions,
    "risk_summary": AiRiskSummary,
}


def validate_ai_schema(schema_name: str, payload: Any) -> dict[str, object]:
    schema = AI_SCHEMA_REGISTRY.get(schema_name)
    if schema is None:
        raise ValidationFailedError("Unknown AI response schema", data={"schema_name": schema_name})
    try:
        model = schema.model_validate(payload)
    except ValidationError as exc:
        raise AiResponseValidationError(str(exc)) from exc
    return model.model_dump(mode="json")


class AiResponseValidationError(ValueError):
    pass
