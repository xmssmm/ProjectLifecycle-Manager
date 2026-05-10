import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  NotificationListQuery,
  NotificationListRead,
  NotificationRead,
  NotificationReadAllResult,
  NotificationUnreadCountRead,
} from '@/types/notifications';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listNotifications(
  query: NotificationListQuery = {},
  client: AxiosInstance = apiClient,
): Promise<NotificationListRead> {
  const response = await client.get<ApiResponse<NotificationListRead>>('/notifications', {
    params: {
      page: query.page,
      page_size: query.pageSize,
      unread: query.unread,
    },
  });
  return response.data.data;
}

export async function getUnreadNotificationCount(
  client: AxiosInstance = apiClient,
): Promise<NotificationUnreadCountRead> {
  const response = await client.get<ApiResponse<NotificationUnreadCountRead>>(
    '/notifications/unread-count',
  );
  return response.data.data;
}

export async function markNotificationRead(
  notificationId: string,
  client: AxiosInstance = apiClient,
): Promise<NotificationRead> {
  const response = await client.post<ApiResponse<NotificationRead>>(
    `/notifications/${notificationId}/read`,
  );
  return response.data.data;
}

export async function markAllNotificationsRead(
  client: AxiosInstance = apiClient,
): Promise<NotificationReadAllResult> {
  const response =
    await client.post<ApiResponse<NotificationReadAllResult>>('/notifications/read-all');
  return response.data.data;
}
