from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.revoke_requests import RevokeRequestStatus, RevokeReviewDecision


class RevokeRequestCreate(BaseModel):
    phase_id: UUID
    reason: str
    keep_documents: bool = True


class RevokeRequestReview(BaseModel):
    decision: RevokeReviewDecision
    review_comment: str | None = None


class RevokeRequestRead(BaseModel):
    id: UUID
    phase_id: UUID
    sub_project_id: UUID
    requester_id: UUID
    reason: str
    keep_documents: bool
    status: RevokeRequestStatus
    reviewer_id: UUID | None
    review_comment: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RevokeRequestListRead(BaseModel):
    items: list[RevokeRequestRead]
    total: int
