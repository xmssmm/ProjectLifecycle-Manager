import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createSubProject,
  addSubProjectMember,
  getSubProject,
  listSubProjectMembers,
  listSubProjects,
  removeSubProjectMember,
  reviewSubProject,
  submitSubProject,
  terminateSubProject,
} from '@/api/subProjects';
import { useAuthStore } from '@/stores/useAuthStore';
import SubProjectDetail from '@/views/sub-project/SubProjectDetail.vue';
import SubProjectEdit from '@/views/sub-project/SubProjectEdit.vue';
import SubProjectList from '@/views/sub-project/SubProjectList.vue';
import SubProjectReview from '@/views/sub-project/SubProjectReview.vue';

vi.mock('@/api/subProjects', () => ({
  addSubProjectMember: vi.fn(),
  createSubProject: vi.fn(),
  getSubProject: vi.fn(),
  listSubProjectMembers: vi.fn(),
  listSubProjects: vi.fn(),
  removeSubProjectMember: vi.fn(),
  reviewSubProject: vi.fn(),
  submitSubProject: vi.fn(),
  terminateSubProject: vi.fn(),
}));

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(),
}));

vi.mock('pdfjs-dist/build/pdf.worker.mjs?url', () => ({ default: 'worker-url' }));

describe('sub project pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    const authStore = useAuthStore();
    authStore.setAccessToken('leader-token');
    authStore.setUser({
      deptId: 'dept-a',
      email: null,
      id: 'leader-1',
      role: 'proj_leader',
      status: 'active',
      username: 'leader',
    });
    vi.mocked(listSubProjects).mockResolvedValue({
      items: [sampleSubProject, closedSubProject],
      page: 1,
      page_size: 20,
      total: 2,
    });
    vi.mocked(getSubProject).mockResolvedValue(sampleSubProject);
    vi.mocked(listSubProjectMembers).mockResolvedValue({
      items: [sampleMember],
      total: 1,
    });
    vi.mocked(createSubProject).mockResolvedValue(sampleSubProject);
    vi.mocked(addSubProjectMember).mockResolvedValue(sampleMember);
    vi.mocked(removeSubProjectMember).mockResolvedValue(sampleMember);
    vi.mocked(submitSubProject).mockResolvedValue(sampleSubProject);
    vi.mocked(reviewSubProject).mockResolvedValue({
      ...sampleSubProject,
      status: 'in_progress',
    });
    vi.mocked(terminateSubProject).mockResolvedValue({
      ...sampleSubProject,
      status: 'terminated',
    });
  });

  it('renders sub project list with status filtering', async () => {
    const wrapper = mount(SubProjectList, { global: { stubs } });
    await flushPromises();

    expect(wrapper.text()).toContain('采购实施');
    expect(wrapper.text()).toContain('历史子项目');

    await wrapper.find('[data-test="filter-closed"]').trigger('click');

    expect(wrapper.text()).not.toContain('采购实施');
    expect(wrapper.text()).toContain('历史子项目');
  });

  it('renders sub project detail and can terminate with a reason', async () => {
    const authStore = useAuthStore();
    authStore.setUser({
      deptId: 'dept-b',
      email: null,
      id: 'manager-1',
      role: 'dept_manager',
      status: 'active',
      username: 'manager',
    });
    const wrapper = mount(SubProjectDetail, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('采购实施');
    await wrapper.find('[data-test="open-terminate"]').trigger('click');
    await wrapper.find('[data-test="terminate-reason"]').setValue('需求取消');
    await wrapper.find('[data-test="confirm-terminate"]').trigger('click');
    await flushPromises();

    expect(terminateSubProject).toHaveBeenCalledWith('sub-1', { reason: '需求取消' });
  });

  it('lets project leader add and remove sub project members', async () => {
    const wrapper = mount(SubProjectDetail, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    expect(listSubProjectMembers).toHaveBeenCalledWith('sub-1');
    expect(wrapper.text()).toContain('member-1');

    await wrapper.find('[data-test="member-user-id"]').setValue('member-2');
    await wrapper.find('[data-test="add-member"]').trigger('click');
    await flushPromises();

    expect(addSubProjectMember).toHaveBeenCalledWith('sub-1', { user_id: 'member-2' });

    await wrapper.find('[data-test="remove-member"]').trigger('click');
    await flushPromises();

    expect(removeSubProjectMember).toHaveBeenCalledWith('sub-1', 'member-1');
  });

  it('validates and creates a sub project before submitting it', async () => {
    const wrapper = mount(SubProjectEdit, { global: { stubs } });

    await wrapper.find('[data-test="submit-sub-project"]').trigger('click');

    expect(wrapper.text()).toContain('子项目名称必填');
    expect(createSubProject).not.toHaveBeenCalled();

    await wrapper.find('[data-test="sub-name"]').setValue('采购实施');
    await wrapper.find('[data-test="sub-main-project"]').setValue('main-1');
    await wrapper.find('[data-test="sub-dept"]').setValue('dept-a');
    await wrapper.find('[data-test="sub-budget"]').setValue('100000.00');
    await wrapper.find('[data-test="sub-plan-end"]').setValue('2026-10-31');
    await wrapper.find('[data-test="submit-sub-project"]').trigger('click');
    await wrapper.find('[data-test="confirm-submit"]').trigger('click');
    await flushPromises();

    expect(createSubProject).toHaveBeenCalledWith({
      budget: '100000.00',
      dept_id: 'dept-a',
      main_project_id: 'main-1',
      name: '采购实施',
      plan_end_date: '2026-10-31',
      remark: null,
    });
    expect(submitSubProject).toHaveBeenCalledWith('sub-1');
  });

  it('handles over-budget review confirmation and resubmits approval', async () => {
    const authStore = useAuthStore();
    authStore.setUser({
      deptId: 'dept-b',
      email: null,
      id: 'manager-1',
      role: 'dept_manager',
      status: 'active',
      username: 'manager',
    });
    vi.mocked(reviewSubProject)
      .mockRejectedValueOnce({
        response: {
          data: {
            code: 3001,
            data: { over_budget_amount: '1000.00' },
            message: '子项目预算超出主项目剩余预算，需二次确认',
          },
        },
      })
      .mockResolvedValueOnce({ ...sampleSubProject, status: 'in_progress' });
    const wrapper = mount(SubProjectReview, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    await wrapper.find('[data-test="sub-review-comment"]').setValue('通过');
    await wrapper.find('[data-test="approve-sub-project"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('超预算');

    await wrapper.find('[data-test="over-budget-reason"]').setValue('专项预算已确认');
    await flushPromises();
    await wrapper.find('[data-test="confirm-over-budget"]').trigger('click');
    await flushPromises();

    expect(reviewSubProject).toHaveBeenLastCalledWith('sub-1', {
      confirm_over_budget: true,
      decision: 'approve',
      over_budget_reason: '专项预算已确认',
      review_comment: '通过',
      updates: null,
    });
  });
});

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
  status: 'pending_review',
  updated_at: '2026-05-10T00:00:00Z',
} as const;

const closedSubProject = {
  ...sampleSubProject,
  id: 'sub-2',
  name: '历史子项目',
  status: 'closed',
} as const;

const sampleMember = {
  created_at: '2026-05-10T00:00:00Z',
  id: 'member-row-1',
  joined_at: '2026-05-10T00:00:00Z',
  role_in_project: 'proj_member',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T00:00:00Z',
  user_id: 'member-1',
} as const;

const stubs = {
  ConfirmDialog: {
    props: ['modelValue', 'message', 'title'],
    template:
      '<section v-if="modelValue" data-test="confirm-dialog">{{ title }}{{ message }}<slot /><button data-test="confirm-submit" @click="$emit(\'confirm\')">确认</button><button data-test="confirm-terminate" @click="$emit(\'confirm\')">中止</button></section>',
  },
  DataTable: {
    props: ['columns', 'loading', 'page', 'pageSize', 'rows', 'total'],
    template:
      '<section><article v-for="row in rows" :key="row.id"><span>{{ row.project_no }}</span><span>{{ row.name }}</span><slot name="status" :row="row" :value="row.status" /><slot name="actions" :row="row" /></article></section>',
  },
  ElAlert: { props: ['title'], template: '<section>{{ title }}</section>' },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDatePicker: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElDescriptions: { template: '<dl><slot /></dl>' },
  ElDescriptionsItem: {
    props: ['label'],
    template: '<div><dt>{{ label }}</dt><dd><slot /></dd></div>',
  },
  ElEmpty: { template: '<section>{{ description }}</section>', props: ['description'] },
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
  ElOption: { template: '<option />' },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElSkeleton: { template: '<section><slot /></section>' },
  PhaseDocumentPanel: { template: '<section />' },
  PhaseProgress: { template: '<section />' },
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
  SearchBar: {
    template:
      "<section><button data-test=\"filter-closed\" @click=\"$emit('search', { status: 'closed', main_project_id: '' })\">closed</button><slot /></section>",
  },
  StatusTag: {
    props: ['status'],
    template: '<span>{{ status === "closed" ? "已结项" : "待审核" }}</span>',
  },
};
