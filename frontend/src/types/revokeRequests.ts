export type RevokeRequestStatus = 'pending' | 'approved' | 'rejected';
export type RevokeReviewDecision = 'approve' | 'reject';

export interface RevokeRequestRead {
  created_at: string;
  id: string;
  phase_id: string;
  reason: string;
  requester_id: string;
  review_comment: string | null;
  reviewed_at: string | null;
  reviewer_id: string | null;
  status: RevokeRequestStatus;
  sub_project_id: string;
  updated_at: string;
}

export interface RevokeRequestListRead {
  items: RevokeRequestRead[];
  total: number;
}

export interface RevokeRequestListQuery {
  status?: RevokeRequestStatus;
}

export interface RevokeRequestCreatePayload {
  phaseId: string;
  reason: string;
}

export interface RevokeRequestReviewPayload {
  decision: RevokeReviewDecision;
  reviewComment?: string | null;
}

export const REVOKE_REQUEST_STATUS_LABELS: Record<RevokeRequestStatus, string> = {
  approved: '已通过',
  pending: '待审核',
  rejected: '已驳回',
};

export const REVOKE_REVIEW_DECISION_LABELS: Record<RevokeReviewDecision, string> = {
  approve: '通过',
  reject: '驳回',
};
