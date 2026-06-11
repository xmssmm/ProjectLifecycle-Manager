import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  RevokeRequestCreatePayload,
  RevokeRequestListQuery,
  RevokeRequestListRead,
  RevokeRequestRead,
  RevokeRequestReviewPayload,
} from '@/types/revokeRequests';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listRevokeRequests(
  query: RevokeRequestListQuery = {},
  client: AxiosInstance = apiClient,
): Promise<RevokeRequestListRead> {
  const response = await client.get<ApiResponse<RevokeRequestListRead>>('/revoke-requests', {
    params: { status: query.status },
  });
  return response.data.data;
}

export async function submitRevokeRequest(
  payload: RevokeRequestCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<RevokeRequestRead> {
  const response = await client.post<ApiResponse<RevokeRequestRead>>('/revoke-requests', {
    keep_documents: payload.keepDocuments,
    phase_id: payload.phaseId,
    reason: payload.reason,
  });
  return response.data.data;
}

export async function reviewRevokeRequest(
  requestId: string,
  payload: RevokeRequestReviewPayload,
  client: AxiosInstance = apiClient,
): Promise<RevokeRequestRead> {
  const response = await client.post<ApiResponse<RevokeRequestRead>>(
    `/revoke-requests/${requestId}/review`,
    {
      decision: payload.decision,
      review_comment: payload.reviewComment || null,
    },
  );
  return response.data.data;
}
