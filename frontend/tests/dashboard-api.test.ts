import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import { getDashboard } from '../src/api/dashboard';

describe('dashboard api', () => {
  it('loads the role scoped dashboard endpoint', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: sampleDashboard,
      message: 'success',
    });

    const result = await getDashboard('finance_manager', client);

    expect(result).toEqual(sampleDashboard);
    expect(calls[0]).toMatchObject({
      method: 'get',
      url: '/dashboard/finance_manager',
    });
  });
});

const sampleDashboard = {
  cache_ttl_seconds: 300,
  charts: {
    paid_vs_budget: [
      { label: 'paid', value: '1200.00' },
      { label: 'budget', value: '3000.00' },
    ],
  },
  generated_at: '2026-05-10T08:00:00Z',
  lists: {
    unpaid_sub_projects: [{ id: 'sub-1', name: '未付款子项目', status: 'in_progress' }],
  },
  metrics: {
    current_month_payment_total: '1200.00',
    total_budget: '3000.00',
    total_paid: '1200.00',
  },
  role_scope: 'finance_manager',
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
