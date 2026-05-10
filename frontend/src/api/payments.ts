import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  PaymentCreatePayload,
  PaymentListQuery,
  PaymentListRead,
  PaymentRead,
} from '@/types/payments';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listPayments(
  subProjectId: string,
  query: PaymentListQuery = {},
  client: AxiosInstance = apiClient,
): Promise<PaymentListRead> {
  const response = await client.get<ApiResponse<PaymentListRead>>(
    `/sub-projects/${subProjectId}/payments`,
    {
      params: {
        page: query.page,
        page_size: query.pageSize,
        payment_type: query.paymentType,
      },
    },
  );
  return response.data.data;
}

export async function createPayment(
  payload: PaymentCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<PaymentRead> {
  const form = new FormData();
  form.append('amount', payload.amount);
  form.append('payment_date', payload.paymentDate);
  if (payload.remark) {
    form.append('remark', payload.remark);
  }
  for (const file of payload.files) {
    form.append('files', file);
  }

  const response = await client.post<ApiResponse<PaymentRead>>(
    `/sub-projects/${payload.subProjectId}/payments`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return response.data.data;
}

export async function getPayment(
  subProjectId: string,
  paymentId: string,
  client: AxiosInstance = apiClient,
): Promise<PaymentRead> {
  const response = await client.get<ApiResponse<PaymentRead>>(
    `/sub-projects/${subProjectId}/payments/${paymentId}`,
  );
  return response.data.data;
}
