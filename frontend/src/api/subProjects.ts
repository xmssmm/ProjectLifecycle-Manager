import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  SubProjectCreatePayload,
  SubProjectListQuery,
  SubProjectListRead,
  SubProjectMemberCreatePayload,
  SubProjectMemberListRead,
  SubProjectMemberRead,
  SubProjectRead,
  SubProjectReviewPayload,
  SubProjectTerminatePayload,
  SubProjectUpdatePayload,
} from '@/types/projects';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export async function listSubProjects(
  query: SubProjectListQuery,
  client: AxiosInstance = apiClient,
): Promise<SubProjectListRead> {
  const response = await client.get<ApiResponse<SubProjectListRead>>('/sub-projects', {
    params: {
      page: query.page,
      page_size: query.pageSize,
    },
  });
  return response.data.data;
}

export async function getSubProject(
  subProjectId: string,
  client: AxiosInstance = apiClient,
): Promise<SubProjectRead> {
  const response = await client.get<ApiResponse<SubProjectRead>>(`/sub-projects/${subProjectId}`);
  return response.data.data;
}

export async function createSubProject(
  payload: SubProjectCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<SubProjectRead> {
  const response = await client.post<ApiResponse<SubProjectRead>>('/sub-projects', payload);
  return response.data.data;
}

export async function updateSubProject(
  subProjectId: string,
  payload: SubProjectUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<SubProjectRead> {
  const response = await client.put<ApiResponse<SubProjectRead>>(
    `/sub-projects/${subProjectId}`,
    payload,
  );
  return response.data.data;
}

export async function submitSubProject(
  subProjectId: string,
  client: AxiosInstance = apiClient,
): Promise<SubProjectRead> {
  const response = await client.post<ApiResponse<SubProjectRead>>(
    `/sub-projects/${subProjectId}/submit`,
  );
  return response.data.data;
}

export async function reviewSubProject(
  subProjectId: string,
  payload: SubProjectReviewPayload,
  client: AxiosInstance = apiClient,
): Promise<SubProjectRead> {
  const response = await client.post<ApiResponse<SubProjectRead>>(
    `/sub-projects/${subProjectId}/review`,
    payload,
  );
  return response.data.data;
}

export async function closeSubProject(
  subProjectId: string,
  client: AxiosInstance = apiClient,
): Promise<SubProjectRead> {
  const response = await client.post<ApiResponse<SubProjectRead>>(
    `/sub-projects/${subProjectId}/close`,
  );
  return response.data.data;
}

export async function terminateSubProject(
  subProjectId: string,
  payload: SubProjectTerminatePayload,
  client: AxiosInstance = apiClient,
): Promise<SubProjectRead> {
  const response = await client.post<ApiResponse<SubProjectRead>>(
    `/sub-projects/${subProjectId}/terminate`,
    payload,
  );
  return response.data.data;
}

export async function listSubProjectMembers(
  subProjectId: string,
  client: AxiosInstance = apiClient,
): Promise<SubProjectMemberListRead> {
  const response = await client.get<ApiResponse<SubProjectMemberListRead>>(
    `/sub-projects/${subProjectId}/members`,
  );
  return response.data.data;
}

export async function addSubProjectMember(
  subProjectId: string,
  payload: SubProjectMemberCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<SubProjectMemberRead> {
  const response = await client.post<ApiResponse<SubProjectMemberRead>>(
    `/sub-projects/${subProjectId}/members`,
    payload,
  );
  return response.data.data;
}

export async function removeSubProjectMember(
  subProjectId: string,
  userId: string,
  client: AxiosInstance = apiClient,
): Promise<SubProjectMemberRead> {
  const response = await client.delete<ApiResponse<SubProjectMemberRead>>(
    `/sub-projects/${subProjectId}/members/${userId}`,
  );
  return response.data.data;
}
