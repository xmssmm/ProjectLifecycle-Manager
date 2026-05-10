import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getDashboard } from '@/api/dashboard';
import { useDashboardStore } from '@/stores/useDashboardStore';
import type { DashboardRead } from '@/types/dashboard';

vi.mock('@/api/dashboard', () => ({
  getDashboard: vi.fn(),
}));

describe('dashboard store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads a role scoped dashboard and records refresh metadata', async () => {
    vi.mocked(getDashboard).mockResolvedValue(sampleDashboard);
    const store = useDashboardStore();

    const result = await store.fetchDashboard('finance_manager');

    expect(getDashboard).toHaveBeenCalledWith('finance_manager');
    expect(result).toEqual(sampleDashboard);
    expect(store.dashboard).toEqual(sampleDashboard);
    expect(store.roleScope).toBe('finance_manager');
    expect(store.lastLoadedAt).toBe('2026-05-10T08:00:00Z');
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
  });
});

const sampleDashboard: DashboardRead = {
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
