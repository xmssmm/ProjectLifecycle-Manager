import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { ProjectRiskRead } from '@/types/projectRisk';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function fetchProjectRisk(
  projectId: string,
  client: AxiosInstance = apiClient,
): Promise<ProjectRiskRead> {
  const response = await client.get<ApiResponse<ProjectRiskRead>>(`/project-risk/${projectId}`);
  return response.data.data;
}
