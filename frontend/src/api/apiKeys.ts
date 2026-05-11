import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  ApiKeyCreatePayload,
  ApiKeyCreateRead,
  ApiKeyListQuery,
  ApiKeyListRead,
  ApiKeyRead,
} from '@/types/apiKeys';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listApiKeys(
  query: ApiKeyListQuery,
  client: AxiosInstance = apiClient,
): Promise<ApiKeyListRead> {
  const response = await client.get<ApiResponse<ApiKeyListRead>>('/api-keys', {
    params: {
      page: query.page,
      page_size: query.pageSize,
    },
  });
  return response.data.data;
}

export async function createApiKey(
  payload: ApiKeyCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<ApiKeyCreateRead> {
  const response = await client.post<ApiResponse<ApiKeyCreateRead>>('/api-keys', {
    expires_at: payload.expiresAt ?? null,
    name: payload.name,
    permissions: payload.permissions,
  });
  return response.data.data;
}

export async function revokeApiKey(
  apiKeyId: string,
  client: AxiosInstance = apiClient,
): Promise<ApiKeyRead> {
  const response = await client.delete<ApiResponse<ApiKeyRead>>(`/api-keys/${apiKeyId}`);
  return response.data.data;
}
