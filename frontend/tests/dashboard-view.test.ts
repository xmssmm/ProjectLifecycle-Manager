import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getDashboard } from '@/api/dashboard';
import { useAuthStore } from '@/stores/useAuthStore';
import type { DashboardRead } from '@/types/dashboard';
import DashboardView from '@/views/dashboard/DashboardView.vue';

const chartMocks = vi.hoisted(() => {
  const chartDispose = vi.fn();
  const chartResize = vi.fn();
  const chartSetOption = vi.fn();
  const chartInit = vi.fn(() => ({
    dispose: chartDispose,
    resize: chartResize,
    setOption: chartSetOption,
  }));
  return { chartDispose, chartInit, chartResize, chartSetOption };
});

vi.mock('echarts', () => ({
  init: chartMocks.chartInit,
}));

vi.mock('@/api/dashboard', () => ({
  getDashboard: vi.fn(),
}));

describe('DashboardView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(getDashboard).mockResolvedValue(sampleDashboard);
    const authStore = useAuthStore();
    authStore.setAccessToken('finance-token');
    authStore.setUser({
      deptId: null,
      email: null,
      id: 'finance-1',
      role: 'finance_manager',
      status: 'active',
      username: 'finance',
    });
  });

  it('loads the current role dashboard, renders metrics, charts, and priority lists', async () => {
    const wrapper = mount(DashboardView, { global: { stubs } });
    await flushPromises();

    expect(getDashboard).toHaveBeenCalledWith('finance_manager');
    expect(wrapper.find('[data-test="dashboard-role-title"]').text()).toContain('财务负责人');
    expect(wrapper.find('[data-test="dashboard-metric-total_paid"]').text()).toContain('1200.00');
    expect(wrapper.find('[data-test="dashboard-chart-paid_vs_budget"]').exists()).toBe(true);
    expect(chartMocks.chartInit).toHaveBeenCalled();
    expect(chartMocks.chartSetOption).toHaveBeenCalled();
    expect(wrapper.find('[data-test="dashboard-list-unpaid_sub_projects"]').text()).toContain(
      '未付款子项目',
    );
  });

  it('shows load errors without surfacing an unhandled view exception', async () => {
    vi.mocked(getDashboard).mockRejectedValue(new Error('Network down'));

    const wrapper = mount(DashboardView, { global: { stubs } });
    await flushPromises();

    expect(wrapper.text()).toContain('Network down');
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

const stubs = {
  ElAlert: { props: ['closable', 'title', 'type'], template: '<section>{{ title }}</section>' },
  ElButton: {
    emits: ['click'],
    props: ['disabled', 'icon', 'loading', 'type'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElIcon: { template: '<i><slot /></i>' },
  ElSkeleton: { props: ['loading'], template: '<section><slot /></section>' },
  RouterLink: { props: ['to'], template: '<a :to="to"><slot /></a>' },
};
