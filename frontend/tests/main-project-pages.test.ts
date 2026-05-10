import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getMainProject, listMainProjects } from '@/api/mainProjects';
import { listSubProjects } from '@/api/subProjects';
import MainProjectDetail from '@/views/main-project/MainProjectDetail.vue';
import MainProjectList from '@/views/main-project/MainProjectList.vue';

vi.mock('@/api/mainProjects', () => ({
  getMainProject: vi.fn(),
  listMainProjects: vi.fn(),
}));

vi.mock('@/api/subProjects', () => ({
  listSubProjects: vi.fn(),
}));

describe('main project pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listMainProjects).mockResolvedValue({
      items: [sampleMainProject, otherProject],
      page: 1,
      page_size: 20,
      total: 2,
    });
    vi.mocked(getMainProject).mockResolvedValue(sampleMainProject);
    vi.mocked(listSubProjects).mockResolvedValue({
      items: [sampleSubProject, otherSubProject],
      page: 1,
      page_size: 100,
      total: 2,
    });
  });

  it('renders main project list with status and department filters', async () => {
    const wrapper = mount(MainProjectList, { global: { stubs } });
    await flushPromises();

    expect(wrapper.text()).toContain('智慧档案平台');
    expect(wrapper.text()).toContain('进行中');

    await wrapper.find('[data-test="filter-closed"]').trigger('click');

    expect(wrapper.text()).not.toContain('智慧档案平台');
    expect(wrapper.text()).toContain('历史项目');
  });

  it('renders project detail timeline and child subprojects', async () => {
    const wrapper = mount(MainProjectDetail, {
      global: { stubs },
      props: { projectId: 'main-1' },
    });
    await flushPromises();

    expect(getMainProject).toHaveBeenCalledWith('main-1');
    expect(wrapper.text()).toContain('Z-2026-0001');
    expect(wrapper.text()).toContain('状态时间线');
    expect(wrapper.text()).toContain('采购实施');
    expect(wrapper.text()).not.toContain('其他子项目');
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

const otherProject = {
  ...sampleMainProject,
  id: 'main-2',
  name: '历史项目',
  project_no: 'Z-2026-0002',
  status: 'closed',
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

const otherSubProject = {
  ...sampleSubProject,
  id: 'sub-2',
  main_project_id: 'main-2',
  name: '其他子项目',
} as const;

const stubs = {
  DataTable: {
    props: ['columns', 'loading', 'page', 'pageSize', 'rows', 'total'],
    template:
      '<section><article v-for="row in rows" :key="row.id"><span>{{ row.project_no }}</span><span>{{ row.name }}</span><slot name="status" :row="row" :value="row.status" /><slot name="actions" :row="row" /></article></section>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElCard: { template: '<section><slot /></section>' },
  ElDescriptions: { template: '<dl><slot /></dl>' },
  ElDescriptionsItem: {
    props: ['label'],
    template: '<div><dt>{{ label }}</dt><dd><slot /></dd></div>',
  },
  ElEmpty: { template: '<section />' },
  ElLink: { template: '<a><slot /></a>' },
  ElOption: { template: '<option />' },
  ElSelect: { template: '<select><slot /></select>' },
  ElSkeleton: { template: '<section><slot /></section>' },
  ElStep: { props: ['title'], template: '<li>{{ title }}</li>' },
  ElSteps: { template: '<ol><slot /></ol>' },
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
  SearchBar: {
    template:
      "<section><button data-test=\"filter-closed\" @click=\"$emit('search', { status: 'closed', dept_id: '' })\">closed</button><slot /></section>",
  },
  StatusTag: {
    props: ['status'],
    template: '<span>{{ status === "in_progress" ? "进行中" : "已结项" }}</span>',
  },
};
