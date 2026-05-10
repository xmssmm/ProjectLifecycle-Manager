import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  SubProjectBatchHandoverItem,
  SubProjectBatchHandoverRead,
  SubProjectHandoverListRead,
  SubProjectHandoverQuery,
  SubProjectListRead,
} from '@/types/projects';
import type {
  PasswordResetPayload,
  PasswordChangePayload,
  UserCreatePayload,
  UserListQuery,
  UserListRead,
  UserRead,
  UserUpdatePayload,
} from '@/types/users';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export async function listUsers(
  query: UserListQuery,
  client: AxiosInstance = apiClient,
): Promise<UserListRead> {
  const response = await client.get<ApiResponse<UserListRead>>('/users', {
    params: {
      page: query.page,
      page_size: query.pageSize,
      role: query.role,
    },
  });
  return response.data.data;
}

export async function getUser(
  userId: string,
  client: AxiosInstance = apiClient,
): Promise<UserRead> {
  const response = await client.get<ApiResponse<UserRead>>(`/users/${userId}`);
  return response.data.data;
}

export async function createUser(
  payload: UserCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<UserRead> {
  const response = await client.post<ApiResponse<UserRead>>('/users', payload);
  return response.data.data;
}

export async function updateUser(
  userId: string,
  payload: UserUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<UserRead> {
  const response = await client.put<ApiResponse<UserRead>>(`/users/${userId}`, payload);
  return response.data.data;
}

export async function disableUser(
  userId: string,
  client: AxiosInstance = apiClient,
): Promise<UserRead> {
  const response = await client.delete<ApiResponse<UserRead>>(`/users/${userId}`);
  return response.data.data;
}

export async function resetUserPassword(
  userId: string,
  payload: PasswordResetPayload,
  client: AxiosInstance = apiClient,
): Promise<UserRead> {
  const response = await client.post<ApiResponse<UserRead>>(
    `/users/${userId}/reset-password`,
    payload,
  );
  return response.data.data;
}

export async function changeOwnPassword(
  payload: PasswordChangePayload,
  client: AxiosInstance = apiClient,
): Promise<UserRead> {
  const response = await client.post<ApiResponse<UserRead>>('/users/me/change-password', payload);
  return response.data.data;
}

export async function listActiveSubProjectsForLeader(
  userId: string,
  client: AxiosInstance = apiClient,
): Promise<SubProjectListRead> {
  const response = await client.get<ApiResponse<SubProjectListRead>>(
    `/users/${userId}/active-sub-projects`,
  );
  return response.data.data;
}

export async function listSubProjectHandovers(
  query: SubProjectHandoverQuery,
  client: AxiosInstance = apiClient,
): Promise<SubProjectHandoverListRead> {
  const response = await client.get<ApiResponse<SubProjectHandoverListRead>>('/users/handovers', {
    params: {
      from_user_id: query.fromUserId,
      page: query.page,
      page_size: query.pageSize,
      sub_project_id: query.subProjectId,
      to_user_id: query.toUserId,
    },
  });
  return response.data.data;
}

export async function batchHandoverSubProjects(
  userId: string,
  payload: SubProjectBatchHandoverItem[],
  client: AxiosInstance = apiClient,
): Promise<SubProjectBatchHandoverRead> {
  const response = await client.post<ApiResponse<SubProjectBatchHandoverRead>>(
    `/users/${userId}/batch-handover`,
    payload,
  );
  return response.data.data;
}
