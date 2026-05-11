import { defineStore } from 'pinia';

import {
  createWebhookEndpoint,
  listWebhookDeadLetters,
  listWebhookEndpoints,
  replayWebhookDelivery,
  setWebhookEndpointActive,
} from '@/api/webhooks';
import type {
  WebhookDeliveryListQuery,
  WebhookDeliveryRead,
  WebhookEndpointCreatePayload,
  WebhookEndpointListQuery,
  WebhookEndpointRead,
} from '@/types/webhooks';

interface WebhookState {
  deadLetters: WebhookDeliveryRead[];
  deadLetterPage: number;
  deadLetterPageSize: number;
  deadLetterTotal: number;
  endpoints: WebhookEndpointRead[];
  endpointPage: number;
  endpointPageSize: number;
  endpointTotal: number;
  loading: boolean;
  submitting: boolean;
}

export const useWebhookStore = defineStore('webhooks', {
  state: (): WebhookState => ({
    deadLetters: [],
    deadLetterPage: 1,
    deadLetterPageSize: 20,
    deadLetterTotal: 0,
    endpoints: [],
    endpointPage: 1,
    endpointPageSize: 20,
    endpointTotal: 0,
    loading: false,
    submitting: false,
  }),
  actions: {
    async fetchEndpoints(query?: Partial<WebhookEndpointListQuery>) {
      this.endpointPage = query?.page ?? this.endpointPage;
      this.endpointPageSize = query?.pageSize ?? this.endpointPageSize;
      this.loading = true;
      try {
        const result = await listWebhookEndpoints({
          page: this.endpointPage,
          pageSize: this.endpointPageSize,
        });
        this.endpoints = result.items;
        this.endpointTotal = result.total;
        this.endpointPage = result.page;
        this.endpointPageSize = result.page_size;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async fetchDeadLetters(query?: Partial<WebhookDeliveryListQuery>) {
      this.deadLetterPage = query?.page ?? this.deadLetterPage;
      this.deadLetterPageSize = query?.pageSize ?? this.deadLetterPageSize;
      this.loading = true;
      try {
        const result = await listWebhookDeadLetters({
          page: this.deadLetterPage,
          pageSize: this.deadLetterPageSize,
        });
        this.deadLetters = result.items;
        this.deadLetterTotal = result.total;
        this.deadLetterPage = result.page;
        this.deadLetterPageSize = result.page_size;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async createEndpoint(payload: WebhookEndpointCreatePayload): Promise<WebhookEndpointRead> {
      this.submitting = true;
      try {
        const endpoint = await createWebhookEndpoint(payload);
        this.upsertEndpoint(endpoint);
        return endpoint;
      } finally {
        this.submitting = false;
      }
    },
    async setEndpointActive(endpointId: string, isActive: boolean): Promise<WebhookEndpointRead> {
      this.submitting = true;
      try {
        const endpoint = await setWebhookEndpointActive(endpointId, isActive);
        this.upsertEndpoint(endpoint);
        return endpoint;
      } finally {
        this.submitting = false;
      }
    },
    async replayDelivery(deliveryId: string): Promise<WebhookDeliveryRead> {
      this.submitting = true;
      try {
        const delivery = await replayWebhookDelivery(deliveryId);
        this.deadLetters = this.deadLetters.filter((item) => item.id !== deliveryId);
        this.deadLetterTotal = Math.max(0, this.deadLetterTotal - 1);
        return delivery;
      } finally {
        this.submitting = false;
      }
    },
    upsertEndpoint(endpoint: WebhookEndpointRead) {
      this.endpoints = [endpoint, ...this.endpoints.filter((item) => item.id !== endpoint.id)];
      this.endpointTotal = this.endpoints.length;
    },
  },
});
