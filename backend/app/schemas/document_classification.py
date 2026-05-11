from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.exceptions import ValidationFailedError


class DocumentClassificationSuggestRequest(BaseModel):
    sub_project_id: UUID
    phase_id: UUID
    file_name: str = Field(min_length=1, max_length=255)
    current_doc_type: str | None = Field(default=None, max_length=64)
    document_id: UUID | None = None
    summary: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def clean_strings(self) -> DocumentClassificationSuggestRequest:
        self.file_name = self.file_name.strip()
        if not self.file_name:
            raise ValidationFailedError("File name is required")
        if self.current_doc_type is not None:
            current_doc_type = self.current_doc_type.strip()
            self.current_doc_type = current_doc_type or None
        if self.summary is not None:
            summary = self.summary.strip()
            self.summary = summary or None
        return self


class DocumentTypeSuggestionRead(BaseModel):
    doc_type: str
    confidence: float
    reason: str
    source: str


class DocumentClassificationRead(BaseModel):
    sub_project_id: UUID
    phase_id: UUID
    file_name: str
    current_doc_type: str | None
    document_id: UUID | None
    suggestions: list[DocumentTypeSuggestionRead]


class DocumentTypeConfirmRequest(BaseModel):
    doc_type: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def clean_doc_type(self) -> DocumentTypeConfirmRequest:
        self.doc_type = self.doc_type.strip()
        if not self.doc_type:
            raise ValidationFailedError("Document type is required")
        return self
