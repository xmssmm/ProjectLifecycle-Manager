import { defineStore } from 'pinia';

import {
  createApiKey as createApiKeyRequest,
  listApiKeys,
  revokeApiKey as revokeApiKeyRequest,
} from '@/api/apiKeys';
import type {
  ApiKeyCreatePayload,
  ApiKeyCreateRead,
  ApiKeyListQuery,
  ApiKeyRead,
} from '@/types/apiKeys';

interface ApiKeyState {
  keys: ApiKeyRead[];
  loading: boolean;
  page: number;
  pageSize: number;
  submitting: boolean;
  total: number;
}

export const useApiKeyStore = defineStore('api-keys', {
  state: (): ApiKeyState => ({
    keys: [],
    loading: false,
    page: 1,
    pageSize: 20,
    submitting: false,
    total: 0,
  }),
  actions: {
    async fetchKeys(query?: Partial<ApiKeyListQuery>) {
      this.page = query?.page ?? this.page;
      this.pageSize = query?.pageSize ?? this.pageSize;
      this.loading = true;
      try {
        const result = await listApiKeys({ page: this.page, pageSize: this.pageSize });
        this.keys = result.items;
        this.total = result.total;
        this.page = result.page;
        this.pageSize = result.page_size;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async createKey(payload: ApiKeyCreatePayload): Promise<ApiKeyCreateRead> {
      this.submitting = true;
      try {
        const result = await createApiKeyRequest(payload);
        this.upsert(result.api_key);
        return result;
      } finally {
        this.submitting = false;
      }
    },
    async revokeKey(apiKeyId: string): Promise<ApiKeyRead> {
      this.submitting = true;
      try {
        const result = await revokeApiKeyRequest(apiKeyId);
        this.upsert(result);
        return result;
      } finally {
        this.submitting = false;
      }
    },
    upsert(apiKey: ApiKeyRead) {
      this.keys = [apiKey, ...this.keys.filter((item) => item.id !== apiKey.id)];
      this.total = this.keys.length;
    },
  },
});
