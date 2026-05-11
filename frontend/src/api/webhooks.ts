import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  WebhookDeliveryListQuery,
  WebhookDeliveryListRead,
  WebhookDeliveryRead,
  WebhookEndpointCreatePayload,
  WebhookEndpointListQuery,
  WebhookEndpointListRead,
  WebhookEndpointRead,
} from '@/types/webhooks';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listWebhookEndpoints(
  query: WebhookEndpointListQuery,
  client: AxiosInstance = apiClient,
): Promise<WebhookEndpointListRead> {
  const response = await client.get<ApiResponse<WebhookEndpointListRead>>('/webhooks', {
    params: {
      page: query.page,
      page_size: query.pageSize,
    },
  });
  return response.data.data;
}

export async function createWebhookEndpoint(
  payload: WebhookEndpointCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<WebhookEndpointRead> {
  const response = await client.post<ApiResponse<WebhookEndpointRead>>('/webhooks', {
    event_types: payload.eventTypes,
    name: payload.name,
    secret: payload.secret,
    url: payload.url,
  });
  return response.data.data;
}

export async function setWebhookEndpointActive(
  endpointId: string,
  isActive: boolean,
  client: AxiosInstance = apiClient,
): Promise<WebhookEndpointRead> {
  const response = await client.patch<ApiResponse<WebhookEndpointRead>>(
    `/webhooks/${endpointId}/active`,
    isActive,
  );
  return response.data.data;
}

export async function listWebhookDeadLetters(
  query: WebhookDeliveryListQuery,
  client: AxiosInstance = apiClient,
): Promise<WebhookDeliveryListRead> {
  const response = await client.get<ApiResponse<WebhookDeliveryListRead>>(
    '/webhooks/dead-letters',
    {
      params: {
        page: query.page,
        page_size: query.pageSize,
      },
    },
  );
  return response.data.data;
}

export async function replayWebhookDelivery(
  deliveryId: string,
  client: AxiosInstance = apiClient,
): Promise<WebhookDeliveryRead> {
  const response = await client.post<ApiResponse<WebhookDeliveryRead>>(
    `/webhooks/deliveries/${deliveryId}/replay`,
  );
  return response.data.data;
}
