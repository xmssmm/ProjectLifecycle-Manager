from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.exceptions import ValidationFailedError


class AiRiskSummary(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    recommendations: list[str] = Field(default_factory=list, max_length=10)


AI_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
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
