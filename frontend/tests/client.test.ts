import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { AxiosError, AxiosHeaders } from 'axios';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createApiClient, installApiInterceptors } from '../src/api/client';
import { useAuthStore } from '../src/stores/useAuthStore';

describe('apiClient', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('uses the configured API base URL and timeout', () => {
    const apiClient = createApiClient('http://localhost:8000/api/v1');

    expect(apiClient.defaults.baseURL).toBe('http://localhost:8000/api/v1');
    expect(apiClient.defaults.timeout).toBe(15000);
    expect(apiClient.defaults.withCredentials).toBe(true);
  });

  it('adds the bearer token to outgoing requests', async () => {
    const apiClient = createApiClient('http://api.local');
    const authStore = useAuthStore();
    authStore.setAccessToken('token-value');
    installApiInterceptors(apiClient);
    apiClient.defaults.adapter = echoAdapter;

    const response = await apiClient.get('/projects');
    const headers = AxiosHeaders.from(response.config.headers);

    expect(headers.get('Authorization')).toBe('Bearer token-value');
  });

  it('clears the token and redirects to login on 401 responses', async () => {
    const apiClient = createApiClient('http://api.local');
    const authStore = useAuthStore();
    const router = { push: vi.fn().mockResolvedValue(undefined) };
    const message = { error: vi.fn(), warning: vi.fn() };
    authStore.setAccessToken('expired-token');
    installApiInterceptors(apiClient, { message, router });
    apiClient.defaults.adapter = failingAdapter(401);

    await expect(apiClient.get('/private')).rejects.toBeInstanceOf(AxiosError);

    expect(authStore.accessToken).toBeNull();
    expect(router.push).toHaveBeenCalledWith({ name: 'login' });
    expect(message.error).toHaveBeenCalledWith('登录状态已过期，请重新登录');
  });

  it('refreshes the access token and retries the original request once', async () => {
    const apiClient = createApiClient('http://api.local');
    const authStore = useAuthStore();
    authStore.setAccessToken('expired-token');
    installApiInterceptors(apiClient);
    const seenAuthorizationHeaders: Array<string | null> = [];
    apiClient.defaults.adapter = async (config) => {
      const headers = AxiosHeaders.from(config.headers);
      if (config.url === '/auth/refresh') {
        return {
          config,
          data: { code: 0, message: 'success', data: { access_token: 'fresh-token' } },
          headers: {},
          status: 200,
          statusText: 'OK',
        };
      }

      seenAuthorizationHeaders.push(headers.get('Authorization')?.toString() ?? null);
      if (seenAuthorizationHeaders.length === 1) {
        const response: AxiosResponse = {
          config: config as InternalAxiosRequestConfig,
          data: {},
          headers: {},
          status: 401,
          statusText: 'Unauthorized',
        };
        throw new AxiosError('expired', undefined, config, undefined, response);
      }

      return {
        config,
        data: { ok: true },
        headers: {},
        status: 200,
        statusText: 'OK',
      };
    };

    const response = await apiClient.get('/private');

    expect(response.status).toBe(200);
    expect(authStore.accessToken).toBe('fresh-token');
    expect(seenAuthorizationHeaders).toEqual(['Bearer expired-token', 'Bearer fresh-token']);
  });

  it('shows clear messages for rate limit and server errors', async () => {
    const message = { error: vi.fn(), warning: vi.fn() };
    const rateLimitedClient = createApiClient('http://api.local');
    installApiInterceptors(rateLimitedClient, { message });
    rateLimitedClient.defaults.adapter = failingAdapter(429);

    await expect(rateLimitedClient.get('/limited')).rejects.toBeInstanceOf(AxiosError);

    const serverErrorClient = createApiClient('http://api.local');
    installApiInterceptors(serverErrorClient, { message });
    serverErrorClient.defaults.adapter = failingAdapter(500);

    await expect(serverErrorClient.get('/broken')).rejects.toBeInstanceOf(AxiosError);

    expect(message.warning).toHaveBeenCalledWith('请求过于频繁，请稍后再试');
    expect(message.error).toHaveBeenCalledWith('系统暂时不可用，请稍后再试');
  });
});

const echoAdapter: AxiosAdapter = async (config) => ({
  config,
  data: {},
  headers: {},
  status: 200,
  statusText: 'OK',
});

function failingAdapter(status: number): AxiosAdapter {
  return async (config) => {
    const response: AxiosResponse = {
      config: config as InternalAxiosRequestConfig,
      data: {},
      headers: {},
      status,
      statusText: 'Error',
    };

    throw new AxiosError('request failed', undefined, config, undefined, response);
  };
}
