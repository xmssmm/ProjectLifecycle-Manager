import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';
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

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export function createApiClient(baseURL = apiBaseUrl): AxiosInstance {
  return axios.create({
    baseURL,
    timeout: 15000,
    withCredentials: true,
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
      const originalRequest = error.config as RetriableRequestConfig | undefined;

      if (
        status === 401 &&
        originalRequest &&
        !originalRequest._retry &&
        !originalRequest.url?.includes('/auth/refresh')
      ) {
        originalRequest._retry = true;
        try {
          const refreshResponse = await client.post('/auth/refresh');
          const nextAccessToken = refreshResponse.data?.data?.access_token as string | undefined;
          if (!nextAccessToken) {
            throw new Error('Missing refreshed access token');
          }
          const authStore = useAuthStore();
          authStore.setAccessToken(nextAccessToken);
          const headers = AxiosHeaders.from(originalRequest.headers);
          headers.set('Authorization', `Bearer ${nextAccessToken}`);
          originalRequest.headers = headers;
          return client(originalRequest);
        } catch {
          const authStore = useAuthStore();
          authStore.clearSession();
          message.error('登录状态已过期，请重新登录');

          try {
            await options.router?.push({ name: 'login' });
          } catch {
            // The login route may not be registered in focused unit tests.
          }
        }
      } else if (status === 401) {
        const authStore = useAuthStore();
        authStore.clearSession();
        message.error('登录状态已过期，请重新登录');

        try {
          await options.router?.push({ name: 'login' });
        } catch {
          // The login route may not be registered in focused unit tests.
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
