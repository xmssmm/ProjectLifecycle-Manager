import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  PasswordResetPayload,
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
