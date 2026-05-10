import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createMainProject,
  getMainProject,
  listMainProjects,
  reviewMainProject,
  submitMainProject,
  updateMainProject,
} from '@/api/mainProjects';
import { listSubProjects } from '@/api/subProjects';
import { useAuthStore } from '@/stores/useAuthStore';
import MainProjectDetail from '@/views/main-project/MainProjectDetail.vue';
import MainProjectEdit from '@/views/main-project/MainProjectEdit.vue';
import MainProjectList from '@/views/main-project/MainProjectList.vue';
import MainProjectReview from '@/views/main-project/MainProjectReview.vue';

vi.mock('@/api/mainProjects', () => ({
  createMainProject: vi.fn(),
  getMainProject: vi.fn(),
  listMainProjects: vi.fn(),
  reviewMainProject: vi.fn(),
  submitMainProject: vi.fn(),
  updateMainProject: vi.fn(),
}));

vi.mock('@/api/subProjects', () => ({
  listSubProjects: vi.fn(),
}));

describe('main project pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    const authStore = useAuthStore();
    authStore.setAccessToken('dept-token');
    authStore.setUser({
      deptId: 'dept-a',
      email: null,
      id: 'user-1',
      role: 'dept_manager',
      status: 'active',
      username: 'manager',
    });
    vi.mocked(listMainProjects).mockResolvedValue({
      items: [sampleMainProject, otherProject],
      page: 1,
      page_size: 20,
      total: 2,
    });
    vi.mocked(getMainProject).mockResolvedValue(sampleMainProject);
    vi.mocked(createMainProject).mockResolvedValue(sampleMainProject);
    vi.mocked(updateMainProject).mockResolvedValue(rejectedProject);
    vi.mocked(submitMainProject).mockResolvedValue({
      ...rejectedProject,
      status: 'pending_review',
    });
    vi.mocked(reviewMainProject).mockResolvedValue({
      ...pendingProject,
      status: 'not_started',
    });
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

  it('validates and submits a new main project after confirmation', async () => {
    const wrapper = mount(MainProjectEdit, { global: { stubs } });

    await wrapper.find('[data-test="submit-for-review"]').trigger('click');

    expect(wrapper.text()).toContain('项目名称必填');
    expect(createMainProject).not.toHaveBeenCalled();

    await wrapper.find('[data-test="project-name"]').setValue('智慧档案平台');
    await wrapper.find('[data-test="project-dept"]').setValue('dept-a');
    await wrapper.find('[data-test="project-budget"]').setValue('500000.00');
    await wrapper.find('[data-test="project-finish"]').setValue('2026-12-31');
    await wrapper.find('[data-test="project-remark"]').setValue('一期');
    await wrapper.find('[data-test="submit-for-review"]').trigger('click');
    await wrapper.find('[data-test="confirm-submit"]').trigger('click');
    await flushPromises();

    expect(createMainProject).toHaveBeenCalledWith({
      dept_id: 'dept-a',
      expected_finish_date: '2026-12-31',
      name: '智慧档案平台',
      remark: '一期',
      total_budget: '500000.00',
    });
    expect(submitMainProject).toHaveBeenCalledWith('main-1');
  });

  it('loads a rejected main project and resubmits it after editing', async () => {
    vi.mocked(getMainProject).mockResolvedValue(rejectedProject);
    const wrapper = mount(MainProjectEdit, {
      global: { stubs },
      props: { projectId: 'main-1' },
    });
    await flushPromises();

    expect(getMainProject).toHaveBeenCalledWith('main-1');
    expect((wrapper.find('[data-test="project-name"]').element as HTMLInputElement).value).toBe(
      '智慧档案平台',
    );

    await wrapper.find('[data-test="project-name"]').setValue('智慧档案平台二期');
    await wrapper.find('[data-test="submit-for-review"]').trigger('click');
    await wrapper.find('[data-test="confirm-submit"]').trigger('click');
    await flushPromises();

    expect(updateMainProject).toHaveBeenCalledWith(
      'main-1',
      expect.objectContaining({
        dept_id: 'dept-a',
        expected_finish_date: '2026-12-31',
        name: '智慧档案平台二期',
        remark: null,
        total_budget: '500000.00',
      }),
    );
    expect(submitMainProject).toHaveBeenCalledWith('main-1');
  });

  it('blocks a department manager from reviewing their own main project', async () => {
    vi.mocked(getMainProject).mockResolvedValue(pendingProject);

    const wrapper = mount(MainProjectReview, {
      global: { stubs },
      props: { projectId: 'main-1' },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('不能审核自己创建的主项目');
    expect(wrapper.find('[data-test="approve-review"]').exists()).toBe(false);
    expect(reviewMainProject).not.toHaveBeenCalled();
  });

  it('shows modified fields and lets admin approve a main project', async () => {
    const authStore = useAuthStore();
    authStore.setUser({
      deptId: null,
      email: null,
      id: 'admin-1',
      role: 'admin',
      status: 'active',
      username: 'admin',
    });
    vi.mocked(getMainProject).mockResolvedValue(pendingProject);

    const wrapper = mount(MainProjectReview, {
      global: { stubs },
      props: { projectId: 'main-1' },
    });
    await flushPromises();

    await wrapper.find('[data-test="review-name"]').setValue('智慧档案平台二期');
    await wrapper.find('[data-test="review-comment"]').setValue('同意立项');

    expect(wrapper.text()).toContain('修改字段');
    expect(wrapper.text()).toContain('项目名称');
    expect(wrapper.text()).toContain('智慧档案平台二期');

    await wrapper.find('[data-test="approve-review"]').trigger('click');
    await flushPromises();

    expect(reviewMainProject).toHaveBeenCalledWith('main-1', {
      decision: 'approve',
      review_comment: '同意立项',
      updates: { name: '智慧档案平台二期' },
    });
  });

  it('submits a rejection with review comment', async () => {
    const authStore = useAuthStore();
    authStore.setUser({
      deptId: 'dept-b',
      email: null,
      id: 'reviewer-1',
      role: 'dept_manager',
      status: 'active',
      username: 'reviewer',
    });
    vi.mocked(getMainProject).mockResolvedValue(pendingProject);

    const wrapper = mount(MainProjectReview, {
      global: { stubs },
      props: { projectId: 'main-1' },
    });
    await flushPromises();

    await wrapper.find('[data-test="review-comment"]').setValue('预算依据不足');
    await wrapper.find('[data-test="reject-review"]').trigger('click');
    await flushPromises();

    expect(reviewMainProject).toHaveBeenCalledWith('main-1', {
      decision: 'reject',
      review_comment: '预算依据不足',
      updates: null,
    });
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

const rejectedProject = {
  ...sampleMainProject,
  status: 'rejected',
} as const;

const pendingProject = {
  ...sampleMainProject,
  status: 'pending_review',
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
  ElAlert: { props: ['title'], template: '<section>{{ title }}</section>' },
  DataTable: {
    props: ['columns', 'loading', 'page', 'pageSize', 'rows', 'total'],
    template:
      '<section><article v-for="row in rows" :key="row.id"><span>{{ row.project_no }}</span><span>{{ row.name }}</span><slot name="status" :row="row" :value="row.status" /><slot name="actions" :row="row" /></article></section>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDatePicker: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElCard: { template: '<section><slot /></section>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: {
    props: ['error', 'label'],
    template: '<label>{{ label }}{{ error }}<slot /></label>',
  },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElInputNumber: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
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
  ConfirmDialog: {
    props: ['modelValue', 'message', 'title'],
    template:
      '<section v-if="modelValue" data-test="submit-confirm-dialog">{{ title }}{{ message }}<button data-test="confirm-submit" @click="$emit(\'confirm\')">确认</button></section>',
  },
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
