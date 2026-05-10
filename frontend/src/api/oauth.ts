import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { TokenPair } from '@/api/auth';
import type {
  OAuthAuthorizationStartRead,
  OAuthBindPayload,
  OAuthBindingRead,
  OAuthCallbackPayload,
  OAuthProviderRead,
  OAuthUnbindResult,
} from '@/types/oauth';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

interface OAuthStartOptions {
  purpose?: 'login' | 'bind';
}

export async function listOAuthProviders(
  client: AxiosInstance = apiClient,
): Promise<OAuthProviderRead[]> {
  const response = await client.get<ApiResponse<OAuthProviderRead[]>>('/oauth/providers');
  return response.data.data;
}

export async function startOAuthLogin(
  provider: string,
  optionsOrClient: OAuthStartOptions | AxiosInstance = {},
  client: AxiosInstance = apiClient,
): Promise<OAuthAuthorizationStartRead> {
  const usingClient = 'request' in optionsOrClient;
  const options = usingClient ? {} : optionsOrClient;
  const resolvedClient = usingClient ? optionsOrClient : client;
  const response = await resolvedClient.get<ApiResponse<OAuthAuthorizationStartRead>>(
    `/oauth/${provider}/login`,
    {
      params: { purpose: options.purpose },
    },
  );
  return response.data.data;
}

export async function completeOAuthCallback(
  payload: OAuthCallbackPayload,
  client: AxiosInstance = apiClient,
): Promise<TokenPair> {
  const response = await client.get<ApiResponse<TokenPair>>(
    `/oauth/${payload.provider}/callback`,
    {
      params: {
        code: payload.code,
        state: payload.state,
      },
      withCredentials: true,
    },
  );
  return response.data.data;
}

export async function listOAuthBindings(
  client: AxiosInstance = apiClient,
): Promise<OAuthBindingRead[]> {
  const response = await client.get<ApiResponse<OAuthBindingRead[]>>('/oauth/bindings');
  return response.data.data;
}

export async function bindOAuthProvider(
  provider: string,
  payload: OAuthBindPayload,
  client: AxiosInstance = apiClient,
): Promise<OAuthBindingRead> {
  const response = await client.post<ApiResponse<OAuthBindingRead>>(
    `/oauth/${provider}/bind`,
    payload,
  );
  return response.data.data;
}

export async function unbindOAuthProvider(
  provider: string,
  client: AxiosInstance = apiClient,
): Promise<OAuthUnbindResult> {
  const response = await client.delete<ApiResponse<OAuthUnbindResult>>(
    `/oauth/${provider}/bind`,
  );
  return response.data.data;
}
