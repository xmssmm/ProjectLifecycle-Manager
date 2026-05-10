import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  candidateReviewHandoverRequest,
  forceHandoverRequest,
  listHandoverRequests,
  reviewHandoverRequest,
  submitHandoverRequest,
} from '@/api/handoverRequests';
import { listSubProjects } from '@/api/subProjects';
import {
  batchHandoverSubProjects,
  listActiveSubProjectsForLeader,
  listSubProjectHandovers,
  listUsers,
} from '@/api/users';
import { useAuthStore } from '@/stores/useAuthStore';
import HandoverHistory from '@/views/admin/HandoverHistory.vue';
import UserHandover from '@/views/admin/UserHandover.vue';
import SelfServiceHandover from '@/views/handover/SelfServiceHandover.vue';

vi.mock('@/api/handoverRequests', () => ({
  candidateReviewHandoverRequest: vi.fn(),
  forceHandoverRequest: vi.fn(),
  listHandoverRequests: vi.fn(),
  reviewHandoverRequest: vi.fn(),
  submitHandoverRequest: vi.fn(),
}));

vi.mock('@/api/subProjects', () => ({
  addSubProjectMember: vi.fn(),
  closeSubProject: vi.fn(),
  createSubProject: vi.fn(),
  getSubProject: vi.fn(),
  listSubProjectMembers: vi.fn(),
  listSubProjects: vi.fn(),
  removeSubProjectMember: vi.fn(),
  reviewSubProject: vi.fn(),
  submitSubProject: vi.fn(),
  terminateSubProject: vi.fn(),
  updateSubProject: vi.fn(),
}));

vi.mock('@/api/users', () => ({
  batchHandoverSubProjects: vi.fn(),
  createUser: vi.fn(),
  disableUser: vi.fn(),
  listActiveSubProjectsForLeader: vi.fn(),
  listSubProjectHandovers: vi.fn(),
  listUsers: vi.fn(),
  resetUserPassword: vi.fn(),
  updateUser: vi.fn(),
}));

describe('UserHandover', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listUsers).mockResolvedValue({
      items: [oldLeader, newLeader],
      page: 1,
      page_size: 20,
      total: 2,
    });
    vi.mocked(listActiveSubProjectsForLeader).mockResolvedValue({
      items: [sampleSubProject],
      page: 1,
      page_size: 1,
      total: 1,
    });
    vi.mocked(batchHandoverSubProjects).mockResolvedValue({
      items: [{ ...sampleSubProject, manager_id: 'leader-2' }],
      total: 1,
    });
    vi.mocked(listSubProjectHandovers).mockResolvedValue({
      items: [sampleHandover],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(listHandoverRequests).mockResolvedValue({
      items: [sampleSelfRequest, sampleCandidateRequest, sampleReviewRequest, sampleTimeoutRequest],
      total: 4,
    });
    vi.mocked(listSubProjects).mockResolvedValue({
      items: [sampleSubProject],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(submitHandoverRequest).mockResolvedValue(sampleSelfRequest);
    vi.mocked(candidateReviewHandoverRequest).mockResolvedValue({
      ...sampleCandidateRequest,
      status: 'pending_review',
    });
    vi.mocked(reviewHandoverRequest).mockResolvedValue({
      ...sampleReviewRequest,
      status: 'approved',
    });
    vi.mocked(forceHandoverRequest).mockResolvedValue({
      ...sampleTimeoutRequest,
      status: 'forced',
    });
  });

  it('loads active projects and batches selected handovers after confirmation', async () => {
    const wrapper = mount(UserHandover, { global: { stubs } });
    await flushPromises();

    expect(listUsers).toHaveBeenCalledWith({ page: 1, pageSize: 100, role: 'proj_leader' });

    await wrapper.find('[data-test="from-user"]').setValue('leader-1');
    await flushPromises();

    expect(listActiveSubProjectsForLeader).toHaveBeenCalledWith('leader-1');
    expect(wrapper.text()).toContain('采购实施');

    await wrapper.find('[data-test="select-sub-project"]').setValue(true);
    await wrapper.find('[data-test="to-user"]').setValue('leader-2');
    await wrapper.find('[data-test="handover-reason"]').setValue('负责人离职');
    await wrapper.find('[data-test="submit-handover"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('确认转交');

    await wrapper.find('[data-test="confirm-handover"]').trigger('click');
    await flushPromises();

    expect(batchHandoverSubProjects).toHaveBeenCalledWith('leader-1', [
      {
        reason: '负责人离职',
        sub_project_id: 'sub-1',
        to_user_id: 'leader-2',
      },
    ]);
  });

  it('renders handover history records', async () => {
    const wrapper = mount(HandoverHistory, { global: { stubs } });
    await flushPromises();

    expect(listSubProjectHandovers).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(wrapper.text()).toContain('handover-1');
    expect(wrapper.text()).toContain('负责人离职');
  });
});

describe('SelfServiceHandover', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listUsers).mockResolvedValue({
      items: [oldLeader, newLeader],
      page: 1,
      page_size: 20,
      total: 2,
    });
    vi.mocked(listHandoverRequests).mockResolvedValue({
      items: [sampleSelfRequest, sampleCandidateRequest, sampleReviewRequest, sampleTimeoutRequest],
      total: 4,
    });
    vi.mocked(listSubProjects).mockResolvedValue({
      items: [sampleSubProject],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(submitHandoverRequest).mockResolvedValue(sampleSelfRequest);
    vi.mocked(candidateReviewHandoverRequest).mockResolvedValue({
      ...sampleCandidateRequest,
      status: 'pending_review',
    });
    vi.mocked(reviewHandoverRequest).mockResolvedValue({
      ...sampleReviewRequest,
      status: 'approved',
    });
    vi.mocked(forceHandoverRequest).mockResolvedValue({
      ...sampleTimeoutRequest,
      status: 'forced',
    });
  });

  it('lets project leaders submit requests and handle candidate review', async () => {
    useAuthStore().setUser({
      deptId: 'dept-a',
      email: null,
      id: 'leader-1',
      role: 'proj_leader',
      status: 'active',
      username: 'old-leader',
    });
    const wrapper = mount(SelfServiceHandover, { global: { stubs } });
    await flushPromises();

    await wrapper.find('[data-test="handover-project"]').setValue(true);
    await wrapper.find('[data-test="self-to-user"]').setValue('leader-2');
    await wrapper.find('[data-test="self-handover-reason"]').setValue('轮岗');
    await wrapper.find('[data-test="submit-self-handover"]').trigger('click');
    await flushPromises();

    expect(submitHandoverRequest).toHaveBeenCalledWith({
      reason: '轮岗',
      subProjectIds: ['sub-1'],
      toUserId: 'leader-2',
    });

    await wrapper.find('[data-test="confirm-candidate"]').trigger('click');
    await flushPromises();

    expect(candidateReviewHandoverRequest).toHaveBeenCalledWith('handover-candidate', {
      decision: 'confirm',
    });
    expect(wrapper.find('[data-test="approve-handover-request"]').exists()).toBe(false);
    expect(wrapper.find('[data-test="force-handover-request"]').exists()).toBe(false);
  });

  it('lets reviewers approve and admins force requests', async () => {
    useAuthStore().setUser({
      deptId: 'dept-a',
      email: null,
      id: 'admin-1',
      role: 'admin',
      status: 'active',
      username: 'admin',
    });
    const wrapper = mount(SelfServiceHandover, { global: { stubs } });
    await flushPromises();

    expect(wrapper.find('[data-test="submit-self-handover"]').exists()).toBe(false);

    await wrapper.find('[data-test="approve-handover-request"]').trigger('click');
    await wrapper.find('[data-test="force-handover-request"]').trigger('click');
    await flushPromises();

    expect(reviewHandoverRequest).toHaveBeenCalledWith('handover-review', {
      decision: 'approve',
      reviewComment: null,
    });
    expect(forceHandoverRequest).toHaveBeenCalledWith('handover-timeout');
  });

  it('hides review actions from project leaders', async () => {
    useAuthStore().setUser({
      deptId: 'dept-a',
      email: null,
      id: 'leader-1',
      role: 'proj_leader',
      status: 'active',
      username: 'old-leader',
    });
    const wrapper = mount(SelfServiceHandover, { global: { stubs } });
    await flushPromises();

    expect(wrapper.find('[data-test="approve-handover-request"]').exists()).toBe(false);
  });
});

const baseUser = {
  created_at: '2026-05-10T00:00:00Z',
  dept_id: null,
  email: null,
  last_login_at: null,
  password_changed_at: '2026-05-10T00:00:00Z',
  role: 'proj_leader',
  sso_required: false,
  status: 'active',
  updated_at: '2026-05-10T00:00:00Z',
} as const;

const oldLeader = {
  ...baseUser,
  id: 'leader-1',
  username: 'old-leader',
} as const;

const newLeader = {
  ...baseUser,
  id: 'leader-2',
  username: 'new-leader',
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

const sampleHandover = {
  created_at: '2026-05-10T00:00:00Z',
  from_user_id: 'leader-1',
  id: 'handover-1',
  operated_at: '2026-05-10T00:00:00Z',
  operator_id: 'admin-1',
  reason: '负责人离职',
  sub_project_id: 'sub-1',
  to_user_id: 'leader-2',
  updated_at: '2026-05-10T00:00:00Z',
} as const;

const sampleSelfRequest = {
  candidate_comment: null,
  candidate_responded_at: null,
  created_at: '2026-05-11T00:00:00Z',
  forced_at: null,
  forced_by_id: null,
  from_user_id: 'leader-1',
  id: 'handover-self',
  reason: '轮岗',
  review_comment: null,
  reviewed_at: null,
  reviewer_id: null,
  status: 'pending_candidate',
  sub_project_ids: ['sub-1'],
  to_user_id: 'leader-2',
  updated_at: '2026-05-11T00:00:00Z',
} as const;

const sampleCandidateRequest = {
  ...sampleSelfRequest,
  from_user_id: 'leader-2',
  id: 'handover-candidate',
  to_user_id: 'leader-1',
} as const;

const sampleReviewRequest = {
  ...sampleSelfRequest,
  id: 'handover-review',
  status: 'pending_review',
} as const;

const sampleTimeoutRequest = {
  ...sampleSelfRequest,
  created_at: '2026-05-01T00:00:00Z',
  id: 'handover-timeout',
  status: 'pending_candidate',
} as const;

const stubs = {
  ConfirmDialog: {
    props: ['modelValue', 'message', 'title'],
    template:
      '<section v-if="modelValue">{{ title }}{{ message }}<slot /><button data-test="confirm-handover" @click="$emit(\'confirm\')">确认</button></section>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElCheckbox: {
    props: ['modelValue'],
    template:
      '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElOption: {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
};
