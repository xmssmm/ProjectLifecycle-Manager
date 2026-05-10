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
