import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { MainProjectListQuery, MainProjectListRead, MainProjectRead } from '@/types/projects';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export async function listMainProjects(
  query: MainProjectListQuery,
  client: AxiosInstance = apiClient,
): Promise<MainProjectListRead> {
  const response = await client.get<ApiResponse<MainProjectListRead>>('/main-projects', {
    params: {
      page: query.page,
      page_size: query.pageSize,
    },
  });
  return response.data.data;
}

export async function getMainProject(
  projectId: string,
  client: AxiosInstance = apiClient,
): Promise<MainProjectRead> {
  const response = await client.get<ApiResponse<MainProjectRead>>(`/main-projects/${projectId}`);
  return response.data.data;
}
