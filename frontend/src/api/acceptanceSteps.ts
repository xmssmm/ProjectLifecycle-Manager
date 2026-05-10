import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  AcceptanceStepCreatePayload,
  AcceptanceStepListRead,
  AcceptanceStepRead,
  AcceptanceStepUpdatePayload,
} from '@/types/acceptanceSteps';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listAcceptanceSteps(
  phaseId: string,
  client: AxiosInstance = apiClient,
): Promise<AcceptanceStepListRead> {
  const response = await client.get<ApiResponse<AcceptanceStepListRead>>(
    `/phases/${phaseId}/acceptance-steps`,
  );
  return response.data.data;
}

export async function createAcceptanceStep(
  phaseId: string,
  payload: AcceptanceStepCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<AcceptanceStepRead> {
  const response = await client.post<ApiResponse<AcceptanceStepRead>>(
    `/phases/${phaseId}/acceptance-steps`,
    {
      description: payload.description || null,
      plan_date: payload.planDate || null,
      responsible_id: payload.responsibleId,
      step_name: payload.stepName,
      step_no: payload.stepNo,
    },
  );
  return response.data.data;
}

export async function updateAcceptanceStep(
  phaseId: string,
  stepId: string,
  payload: AcceptanceStepUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<AcceptanceStepRead> {
  const response = await client.put<ApiResponse<AcceptanceStepRead>>(
    `/phases/${phaseId}/acceptance-steps/${stepId}`,
    {
      status: payload.status,
    },
  );
  return response.data.data;
}
