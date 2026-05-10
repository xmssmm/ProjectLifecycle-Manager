import axios, { AxiosError, AxiosHeaders, type AxiosInstance } from 'axios';
import { ElMessage } from 'element-plus';
import type { Router } from 'vue-router';

import { useAuthStore } from '@/stores/useAuthStore';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

interface MessageService {
  error(message: string): void;
  warning(message: string): void;
}

interface ApiInterceptorOptions {
  message?: MessageService;
  router?: Pick<Router, 'push'>;
}

export function createApiClient(baseURL = apiBaseUrl): AxiosInstance {
  return axios.create({
    baseURL,
    timeout: 15000,
  });
}

export function installApiInterceptors(
  client: AxiosInstance,
  options: ApiInterceptorOptions = {},
): void {
  const message = options.message ?? ElMessage;

  client.interceptors.request.use((config) => {
    const authStore = useAuthStore();

    if (authStore.accessToken) {
      const headers = AxiosHeaders.from(config.headers);
      headers.set('Authorization', `Bearer ${authStore.accessToken}`);
      config.headers = headers;
    }

    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const status = error.response?.status;

      if (status === 401) {
        const authStore = useAuthStore();
        authStore.setAccessToken(null);
        message.error('登录状态已过期，请重新登录');

        try {
          await options.router?.push({ name: 'login' });
        } catch {
          // The login route is added by the auth feature task.
        }
      } else if (status === 429) {
        message.warning('请求过于频繁，请稍后再试');
      } else if (status && status >= 500) {
        message.error('系统暂时不可用，请稍后再试');
      }

      return Promise.reject(error);
    },
  );
}

export const apiClient = createApiClient();
