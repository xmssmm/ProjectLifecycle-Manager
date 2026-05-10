import { defineStore } from 'pinia';

import {
  candidateReviewHandoverRequest,
  forceHandoverRequest,
  listHandoverRequests,
  reviewHandoverRequest,
  submitHandoverRequest,
} from '@/api/handoverRequests';
import type {
  HandoverCandidateReviewPayload,
  HandoverRequestCreatePayload,
  HandoverRequestListQuery,
  HandoverRequestRead,
  HandoverReviewPayload,
} from '@/types/handoverRequests';

interface HandoverRequestState {
  loading: boolean;
  requests: HandoverRequestRead[];
  submitting: boolean;
  total: number;
}

export const useHandoverRequestStore = defineStore('handover-requests', {
  state: (): HandoverRequestState => ({
    loading: false,
    requests: [],
    submitting: false,
    total: 0,
  }),
  actions: {
    async fetchRequests(query: HandoverRequestListQuery = {}) {
      this.loading = true;
      try {
        const result = await listHandoverRequests(query);
        this.requests = result.items;
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async submitRequest(payload: HandoverRequestCreatePayload) {
      this.submitting = true;
      try {
        const request = await submitHandoverRequest(payload);
        this.upsertRequest(request);
        return request;
      } finally {
        this.submitting = false;
      }
    },
    async candidateReview(requestId: string, payload: HandoverCandidateReviewPayload) {
      const request = await candidateReviewHandoverRequest(requestId, payload);
      this.upsertRequest(request);
      return request;
    },
    async reviewRequest(requestId: string, payload: HandoverReviewPayload) {
      const request = await reviewHandoverRequest(requestId, payload);
      this.upsertRequest(request);
      return request;
    },
    async forceRequest(requestId: string) {
      const request = await forceHandoverRequest(requestId);
      this.upsertRequest(request);
      return request;
    },
    upsertRequest(request: HandoverRequestRead) {
      this.requests = [
        request,
        ...this.requests.filter((item) => item.id !== request.id),
      ];
      this.total = this.requests.length;
    },
  },
});
