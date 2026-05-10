export type HandoverRequestStatus =
  | 'pending_candidate'
  | 'candidate_rejected'
  | 'pending_review'
  | 'review_rejected'
  | 'approved'
  | 'forced';

export type HandoverCandidateDecision = 'confirm' | 'reject';
export type HandoverReviewDecision = 'approve' | 'reject';

export interface HandoverRequestRead {
  candidate_comment: string | null;
  candidate_responded_at: string | null;
  created_at: string;
  forced_at: string | null;
  forced_by_id: string | null;
  from_user_id: string;
  id: string;
  reason: string;
  review_comment: string | null;
  reviewed_at: string | null;
  reviewer_id: string | null;
  status: HandoverRequestStatus;
  sub_project_ids: readonly string[];
  to_user_id: string;
  updated_at: string;
}

export interface HandoverRequestListRead {
  items: HandoverRequestRead[];
  total: number;
}

export interface HandoverRequestListQuery {
  status?: HandoverRequestStatus;
}

export interface HandoverRequestCreatePayload {
  reason: string;
  subProjectIds: string[];
  toUserId: string;
}

export interface HandoverCandidateReviewPayload {
  comment?: string | null;
  decision: HandoverCandidateDecision;
}

export interface HandoverReviewPayload {
  decision: HandoverReviewDecision;
  reviewComment?: string | null;
}

export const HANDOVER_REQUEST_STATUS_LABELS: Record<HandoverRequestStatus, string> = {
  approved: '已通过',
  candidate_rejected: '候选人已拒绝',
  forced: '已强制转交',
  pending_candidate: '待候选人确认',
  pending_review: '待审核',
  review_rejected: '审核已驳回',
};
