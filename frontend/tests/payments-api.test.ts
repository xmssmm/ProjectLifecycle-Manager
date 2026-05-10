import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import { createPayment, getPayment, listPayments, reversePayment } from '../src/api/payments';

describe('payments api', () => {
  it('supports list, multipart create, and detail endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: { items: [samplePayment], page: 2, page_size: 10, total: 12 },
    });

    await listPayments('sub-1', { page: 2, pageSize: 10, paymentType: 'normal' }, client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: samplePayment,
    });
    await createPayment(
      {
        amount: '120.50',
        confirmOverBudget: true,
        files: [new File(['%PDF-1.7'], 'voucher.pdf', { type: 'application/pdf' })],
        overBudgetReason: 'approved budget',
        paymentDate: '2026-05-10',
        remark: 'first payment',
        subProjectId: 'sub-1',
      },
      client,
    );
    await reversePayment(
      {
        remark: 'wrong amount',
        reversesPaymentId: 'pay-1',
        subProjectId: 'sub-1',
      },
      client,
    );
    await getPayment('sub-1', 'pay-1', client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { page: 2, page_size: 10, payment_type: 'normal' },
      url: '/sub-projects/sub-1/payments',
    });
    expect(calls[1]).toMatchObject({
      method: 'post',
      url: '/sub-projects/sub-1/payments',
    });
    expect(calls[1].data).toBeInstanceOf(FormData);
    expect((calls[1].data as FormData).get('confirm_over_budget')).toBe('true');
    expect((calls[1].data as FormData).get('over_budget_reason')).toBe('approved budget');
    expect(calls[2]).toMatchObject({
      method: 'post',
      url: '/sub-projects/sub-1/payments',
    });
    expect((calls[2].data as FormData).get('payment_type')).toBe('reversal');
    expect((calls[2].data as FormData).get('reverses_payment_id')).toBe('pay-1');
    expect((calls[2].data as FormData).get('remark')).toBe('wrong amount');
    expect(calls[3]).toMatchObject({
      method: 'get',
      url: '/sub-projects/sub-1/payments/pay-1',
    });
  });
});

const samplePayment = {
  amount: '120.50',
  created_at: '2026-05-10T00:00:00Z',
  id: 'pay-1',
  operator_id: 'finance-1',
  payment_date: '2026-05-10',
  payment_no: 'Z-2026-0001-ZX-001-PAY-001',
  payment_type: 'normal',
  remark: 'first payment',
  reverses_payment_id: null,
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T00:00:00Z',
};

function recordingAdapter(calls: AxiosRequestConfig[], data: unknown): AxiosAdapter {
  return async (config) => {
    calls.push(config);
    return {
      config,
      data,
      headers: {},
      status: 200,
      statusText: 'OK',
    };
  };
}
