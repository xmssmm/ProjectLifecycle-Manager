import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { UserRole, UserStatus } from '@/types/users';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AccessTokenPayload {
  access_token: string;
  token_type: string;
}

export interface CurrentUserPayload {
  dept_id: string | null;
  email: string | null;
  id: string;
  permissions?: string[];
  role: UserRole;
  status: UserStatus;
  timezone: string;
  username: string;
}

export async function login(
  payload: LoginPayload,
  client: AxiosInstance = apiClient,
): Promise<TokenPair> {
  const response = await client.post<ApiResponse<TokenPair>>('/auth/login', payload, {
    withCredentials: true,
  });
  return response.data.data;
}

export async function refreshAccessToken(
  client: AxiosInstance = apiClient,
): Promise<AccessTokenPayload> {
  const response = await client.post<ApiResponse<AccessTokenPayload>>('/auth/refresh', undefined, {
    withCredentials: true,
  });
  return response.data.data;
}

export async function logout(client: AxiosInstance = apiClient): Promise<void> {
  await client.post('/auth/logout', undefined, { withCredentials: true });
}

export async function getCurrentUser(
  client: AxiosInstance = apiClient,
): Promise<CurrentUserPayload> {
  const response = await client.get<ApiResponse<CurrentUserPayload>>('/auth/me', {
    withCredentials: true,
  });
  return response.data.data;
}
