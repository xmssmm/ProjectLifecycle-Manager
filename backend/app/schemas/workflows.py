from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CodeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
NameText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
RuleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class WorkflowRequiredDocument(BaseModel):
    doc_type: CodeText
    requirement: Literal["required", "conditional", "optional"]
    qty_rule: RuleText
    procurement_type: Literal["inquiry", "bidding", "single_source"] | None = None

    model_config = ConfigDict(extra="forbid")


class WorkflowPhaseDefinition(BaseModel):
    key: CodeText
    name: NameText
    order: int = Field(ge=1)
    required_documents: list[WorkflowRequiredDocument] = Field(default_factory=list)
    allow_parallel: bool = False
    entry_rules: dict[str, object] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class WorkflowTemplateVersionCreate(BaseModel):
    phase_definitions: list[WorkflowPhaseDefinition] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_phase_definitions(self) -> Self:
        keys = [phase.key for phase in self.phase_definitions]
        duplicate_keys = {key for key in keys if keys.count(key) > 1}
        if duplicate_keys:
            raise ValueError(f"duplicate phase key: {sorted(duplicate_keys)[0]}")

        orders = sorted(phase.order for phase in self.phase_definitions)
        expected_orders = list(range(1, len(self.phase_definitions) + 1))
        if orders != expected_orders:
            raise ValueError("phase order must start at 1 and be continuous")

        return self
