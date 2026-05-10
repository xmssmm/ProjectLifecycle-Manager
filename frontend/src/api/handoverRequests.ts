import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  HandoverCandidateReviewPayload,
  HandoverRequestCreatePayload,
  HandoverRequestListQuery,
  HandoverRequestListRead,
  HandoverRequestRead,
  HandoverReviewPayload,
} from '@/types/handoverRequests';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listHandoverRequests(
  query: HandoverRequestListQuery = {},
  client: AxiosInstance = apiClient,
): Promise<HandoverRequestListRead> {
  const response = await client.get<ApiResponse<HandoverRequestListRead>>('/handover-requests', {
    params: { status: query.status },
  });
  return response.data.data;
}

export async function submitHandoverRequest(
  payload: HandoverRequestCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<HandoverRequestRead> {
  const response = await client.post<ApiResponse<HandoverRequestRead>>('/handover-requests', {
    reason: payload.reason,
    sub_project_ids: payload.subProjectIds,
    to_user_id: payload.toUserId,
  });
  return response.data.data;
}

export async function candidateReviewHandoverRequest(
  requestId: string,
  payload: HandoverCandidateReviewPayload,
  client: AxiosInstance = apiClient,
): Promise<HandoverRequestRead> {
  const response = await client.post<ApiResponse<HandoverRequestRead>>(
    `/handover-requests/${requestId}/candidate-review`,
    {
      comment: payload.comment ?? null,
      decision: payload.decision,
    },
  );
  return response.data.data;
}

export async function reviewHandoverRequest(
  requestId: string,
  payload: HandoverReviewPayload,
  client: AxiosInstance = apiClient,
): Promise<HandoverRequestRead> {
  const response = await client.post<ApiResponse<HandoverRequestRead>>(
    `/handover-requests/${requestId}/review`,
    {
      decision: payload.decision,
      review_comment: payload.reviewComment ?? null,
    },
  );
  return response.data.data;
}

export async function forceHandoverRequest(
  requestId: string,
  client: AxiosInstance = apiClient,
): Promise<HandoverRequestRead> {
  const response = await client.post<ApiResponse<HandoverRequestRead>>(
    `/handover-requests/${requestId}/force`,
  );
  return response.data.data;
}
