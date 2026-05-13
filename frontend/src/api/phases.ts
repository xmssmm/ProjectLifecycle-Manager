import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  PhaseDetailRead,
  PhaseListQuery,
  PhaseListRead,
  PhasePromotionRead,
  PhaseRead,
  ProcurementType,
} from '@/types/phases';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listPhases(
  query: PhaseListQuery,
  client: AxiosInstance = apiClient,
): Promise<PhaseListRead> {
  const response = await client.get<ApiResponse<PhaseListRead>>('/phases', {
    params: { sub_project_id: query.subProjectId },
  });
  return response.data.data;
}

export async function getPhase(
  phaseId: string,
  client: AxiosInstance = apiClient,
): Promise<PhaseDetailRead> {
  const response = await client.get<ApiResponse<PhaseDetailRead>>(`/phases/${phaseId}`);
  return response.data.data;
}

export async function promotePhase(
  phaseId: string,
  client: AxiosInstance = apiClient,
): Promise<PhasePromotionRead> {
  const response = await client.post<ApiResponse<PhasePromotionRead>>(`/phases/${phaseId}/promote`);
  return response.data.data;
}

export async function updateProcurementType(
  phaseId: string,
  procurementType: ProcurementType,
  client: AxiosInstance = apiClient,
): Promise<PhaseRead> {
  const response = await client.put<ApiResponse<PhaseRead>>(
    `/phases/${phaseId}/procurement-type`,
    { procurement_type: procurementType },
  );
  return response.data.data;
}
