import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getMainProject, getProjectProgressFunnel } from '@/api/mainProjects';
import { listSubProjects } from '@/api/subProjects';
import { useAuthStore } from '@/stores/useAuthStore';
import type { ProjectProgressFunnelRead } from '@/types/projects';
import MainProjectDetail from '@/views/main-project/MainProjectDetail.vue';

const chartMocks = vi.hoisted(() => {
  const chartDispose = vi.fn();
  const chartOff = vi.fn();
  const chartResize = vi.fn();
  const chartSetOption = vi.fn();
  const chartOn = vi.fn();
  const chartInit = vi.fn(() => ({
    dispose: chartDispose,
    off: chartOff,
    on: chartOn,
    resize: chartResize,
    setOption: chartSetOption,
  }));
  return { chartDispose, chartInit, chartOff, chartOn, chartResize, chartSetOption };
});

vi.mock('echarts', () => ({
  init: chartMocks.chartInit,
}));

vi.mock('@/api/mainProjects', () => ({
  createMainProject: vi.fn(),
  getMainProject: vi.fn(),
  getProjectProgressFunnel: vi.fn(),
  listMainProjects: vi.fn(),
  reviewMainProject: vi.fn(),
  submitMainProject: vi.fn(),
  updateMainProject: vi.fn(),
}));

vi.mock('@/api/subProjects', () => ({
  listSubProjects: vi.fn(),
}));

describe('MainProjectDetail progress funnel', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    const authStore = useAuthStore();
    authStore.setAccessToken('dept-token');
    authStore.setUser({
      deptId: 'dept-a',
      email: null,
      id: 'manager-1',
      role: 'dept_manager',
      status: 'active',
      username: 'manager',
    });
    vi.mocked(getMainProject).mockResolvedValue(sampleMainProject);
    vi.mocked(listSubProjects).mockResolvedValue({
      items: [sampleSubProject],
      page: 1,
      page_size: 100,
      total: 1,
    });
    vi.mocked(getProjectProgressFunnel).mockResolvedValue(sampleFunnel);
  });

  it('renders the project progress funnel and drills into clicked phases', async () => {
    const wrapper = mount(MainProjectDetail, {
      global: { stubs },
      props: { projectId: 'main-1' },
    });
    await flushPromises();

    expect(getProjectProgressFunnel).toHaveBeenCalledWith('main-1');
    expect(wrapper.text()).toContain('项目进度漏斗');
    expect(wrapper.find('[data-test="progress-funnel-chart"]').exists()).toBe(true);
    expect(chartMocks.chartInit).toHaveBeenCalled();
    expect(chartMocks.chartSetOption).toHaveBeenCalled();

    await wrapper.find('[data-test="progress-funnel-phase-2"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-test="progress-funnel-drill-list"]').text()).toContain('采购实施');
    expect(wrapper.find('[data-test="progress-funnel-drill-list"]').text()).not.toContain(
      '立项准备',
    );
  });
});

const sampleMainProject = {
  created_at: '2026-05-10T00:00:00Z',
  creator_id: 'user-1',
  dept_id: 'dept-a',
  expected_finish_date: '2026-12-31',
  id: 'main-1',
  name: '智慧档案平台',
  project_no: 'Z-2026-0001',
  remark: null,
  spent_amount: '0.00',
  status: 'in_progress',
  total_budget: '500000.00',
  updated_at: '2026-05-10T00:00:00Z',
} as const;

const sampleSubProject = {
  actual_end_date: null,
  budget: '100000.00',
  created_at: '2026-05-10T00:00:00Z',
  creator_id: 'leader-1',
  dept_id: 'dept-a',
  id: 'sub-1',
  main_project_id: 'main-1',
  manager_id: 'leader-1',
  name: '采购实施',
  plan_end_date: '2026-10-31',
  project_no: 'Z-2026-0001-ZX-001',
  remark: null,
  spent_amount: '0.00',
  status: 'in_progress',
  updated_at: '2026-05-10T00:00:00Z',
} as const;

const sampleFunnel: ProjectProgressFunnelRead = {
  items: [
    {
      code: 'initiation',
      name: '立项',
      phase_no: 1,
      sub_project_count: 1,
      sub_projects: [
        {
          id: 'sub-2',
          name: '立项准备',
          phase_status: 'in_progress',
          project_no: 'Z-2026-0001-ZX-002',
          status: 'in_progress',
        },
      ],
    },
    {
      code: 'procurement',
      name: '采购',
      phase_no: 2,
      sub_project_count: 1,
      sub_projects: [
        {
          id: 'sub-1',
          name: '采购实施',
          phase_status: 'in_progress',
          project_no: 'Z-2026-0001-ZX-001',
          status: 'in_progress',
        },
      ],
    },
  ],
  main_project_id: 'main-1',
  total_sub_projects: 2,
};

const stubs = {
  ConfirmDialog: { template: '<section />' },
  DataTable: {
    props: ['rows'],
    template: '<section><article v-for="row in rows" :key="row.id">{{ row.name }}</article></section>',
  },
  ElButton: {
    emits: ['click'],
    props: ['type'],
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  },
  ElDescriptions: { template: '<dl><slot /></dl>' },
  ElDescriptionsItem: { props: ['label'], template: '<div>{{ label }}<slot /></div>' },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElProgress: { props: ['percentage'], template: '<progress>{{ percentage }}</progress>' },
  ElSkeleton: { template: '<section><slot /></section>' },
  ElStep: { props: ['title'], template: '<li>{{ title }}</li>' },
  ElSteps: { template: '<ol><slot /></ol>' },
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
  StatusTag: { props: ['status'], template: '<span>{{ status }}</span>' },
};
