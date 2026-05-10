import enum
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.handover_requests import HandoverRequestStatus


class HandoverCandidateDecision(enum.StrEnum):
    confirm = "confirm"
    reject = "reject"


class HandoverReviewDecision(enum.StrEnum):
    approve = "approve"
    reject = "reject"


ReasonText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class HandoverRequestCreate(BaseModel):
    sub_project_ids: list[UUID] = Field(min_length=1)
    to_user_id: UUID
    reason: ReasonText

    model_config = ConfigDict(extra="forbid")


class HandoverCandidateReview(BaseModel):
    decision: HandoverCandidateDecision
    comment: str | None = None

    model_config = ConfigDict(extra="forbid")


class HandoverReviewRequest(BaseModel):
    decision: HandoverReviewDecision
    review_comment: str | None = None

    model_config = ConfigDict(extra="forbid")


class HandoverRequestRead(BaseModel):
    id: UUID
    from_user_id: UUID
    to_user_id: UUID
    sub_project_ids: list[UUID]
    reason: str
    status: HandoverRequestStatus
    candidate_comment: str | None
    candidate_responded_at: datetime | None
    reviewer_id: UUID | None
    review_comment: str | None
    reviewed_at: datetime | None
    forced_by_id: UUID | None
    forced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class HandoverRequestListRead(BaseModel):
    items: list[HandoverRequestRead]
    total: int
