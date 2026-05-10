import { defineStore } from 'pinia';

import { createPayment as createPaymentRequest, getPayment, listPayments } from '@/api/payments';
import type { PaymentCreatePayload, PaymentListQuery, PaymentRead } from '@/types/payments';

interface PaymentState {
  currentPayment: PaymentRead | null;
  detailLoading: boolean;
  listQuery: PaymentListQuery;
  loading: boolean;
  page: number;
  pageSize: number;
  payments: PaymentRead[];
  total: number;
}

export const usePaymentStore = defineStore('payments', {
  state: (): PaymentState => ({
    currentPayment: null,
    detailLoading: false,
    listQuery: { page: 1, pageSize: 20 },
    loading: false,
    page: 1,
    pageSize: 20,
    payments: [],
    total: 0,
  }),
  actions: {
    async fetchPayments(subProjectId: string, query?: PaymentListQuery) {
      const nextQuery = query ?? this.listQuery;
      this.loading = true;
      this.listQuery = nextQuery;
      try {
        const result = await listPayments(subProjectId, nextQuery);
        this.payments = result.items;
        this.page = result.page;
        this.pageSize = result.page_size;
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async fetchPaymentDetail(subProjectId: string, paymentId: string) {
      this.detailLoading = true;
      try {
        const payment = await getPayment(subProjectId, paymentId);
        this.currentPayment = payment;
        this.upsertPayment(payment);
        return payment;
      } finally {
        this.detailLoading = false;
      }
    },
    async createPayment(payload: PaymentCreatePayload) {
      const payment = await createPaymentRequest(payload);
      this.currentPayment = payment;
      this.upsertPayment(payment);
      return payment;
    },
    upsertPayment(payment: PaymentRead) {
      const existingIndex = this.payments.findIndex((item) => item.id === payment.id);
      if (existingIndex >= 0) {
        this.payments.splice(existingIndex, 1, payment);
        return;
      }
      this.payments = [payment, ...this.payments];
      this.total = Math.max(this.total + 1, this.payments.length);
    },
  },
});
