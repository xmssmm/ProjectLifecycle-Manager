import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  MainProjectCreatePayload,
  MainProjectListQuery,
  MainProjectListRead,
  MainProjectRead,
  MainProjectReviewPayload,
  MainProjectUpdatePayload,
} from '@/types/projects';

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

export async function createMainProject(
  payload: MainProjectCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<MainProjectRead> {
  const response = await client.post<ApiResponse<MainProjectRead>>('/main-projects', payload);
  return response.data.data;
}

export async function updateMainProject(
  projectId: string,
  payload: MainProjectUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<MainProjectRead> {
  const response = await client.put<ApiResponse<MainProjectRead>>(
    `/main-projects/${projectId}`,
    payload,
  );
  return response.data.data;
}

export async function submitMainProject(
  projectId: string,
  client: AxiosInstance = apiClient,
): Promise<MainProjectRead> {
  const response = await client.post<ApiResponse<MainProjectRead>>(
    `/main-projects/${projectId}/submit`,
  );
  return response.data.data;
}

export async function reviewMainProject(
  projectId: string,
  payload: MainProjectReviewPayload,
  client: AxiosInstance = apiClient,
): Promise<MainProjectRead> {
  const response = await client.post<ApiResponse<MainProjectRead>>(
    `/main-projects/${projectId}/review`,
    payload,
  );
  return response.data.data;
}
