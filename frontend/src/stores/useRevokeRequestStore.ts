import { defineStore } from 'pinia';

import {
  listRevokeRequests,
  reviewRevokeRequest as reviewRevokeRequestApi,
  submitRevokeRequest as submitRevokeRequestApi,
} from '@/api/revokeRequests';
import type {
  RevokeRequestCreatePayload,
  RevokeRequestListQuery,
  RevokeRequestRead,
  RevokeRequestReviewPayload,
} from '@/types/revokeRequests';

interface RevokeRequestState {
  listQuery: RevokeRequestListQuery;
  loading: boolean;
  requests: RevokeRequestRead[];
  reviewingId: string | null;
  submitting: boolean;
  total: number;
}

export const useRevokeRequestStore = defineStore('revokeRequests', {
  state: (): RevokeRequestState => ({
    listQuery: {},
    loading: false,
    requests: [],
    reviewingId: null,
    submitting: false,
    total: 0,
  }),
  actions: {
    async fetchRequests(query: RevokeRequestListQuery = {}) {
      this.loading = true;
      this.listQuery = query;
      try {
        const result = await listRevokeRequests(query);
        this.requests = result.items;
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async submitRequest(payload: RevokeRequestCreatePayload) {
      this.submitting = true;
      try {
        const request = await submitRevokeRequestApi(payload);
        this.upsertRequest(request);
        return request;
      } finally {
        this.submitting = false;
      }
    },
    async reviewRequest(requestId: string, payload: RevokeRequestReviewPayload) {
      this.reviewingId = requestId;
      try {
        const request = await reviewRevokeRequestApi(requestId, payload);
        this.upsertRequest(request);
        return request;
      } finally {
        this.reviewingId = null;
      }
    },
    upsertRequest(request: RevokeRequestRead) {
      const existingIndex = this.requests.findIndex((item) => item.id === request.id);
      if (existingIndex >= 0) {
        this.requests.splice(existingIndex, 1, request);
      } else {
        this.requests = [request, ...this.requests];
      }
      this.total = Math.max(this.total, this.requests.length);
    },
  },
});
