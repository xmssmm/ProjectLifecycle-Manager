import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listPhases } from '@/api/phases';
import { listRevokeRequests, reviewRevokeRequest, submitRevokeRequest } from '@/api/revokeRequests';
import { useAuthStore } from '@/stores/useAuthStore';
import type { PhaseRead } from '@/types/phases';
import type { RevokeRequestRead } from '@/types/revokeRequests';
import RevokeApply from '@/views/revoke/RevokeApply.vue';
import RevokeReview from '@/views/revoke/RevokeReview.vue';

vi.mock('@/api/phases', () => ({
  getPhase: vi.fn(),
  listPhases: vi.fn(),
  promotePhase: vi.fn(),
  updateProcurementType: vi.fn(),
}));

vi.mock('@/api/revokeRequests', () => ({
  listRevokeRequests: vi.fn(),
  reviewRevokeRequest: vi.fn(),
  submitRevokeRequest: vi.fn(),
}));

describe('revoke pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listPhases).mockResolvedValue({ items: [completedPhase, activePhase], total: 2 });
    vi.mocked(listRevokeRequests).mockResolvedValue({ items: [pendingRequest], total: 1 });
    vi.mocked(submitRevokeRequest).mockResolvedValue(pendingRequest);
    vi.mocked(reviewRevokeRequest).mockResolvedValue(approvedRequest);
  });

  it('lets project leader submit a revoke request and view own requests', async () => {
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
    const wrapper = mount(RevokeApply, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    expect(listPhases).toHaveBeenCalledWith({ subProjectId: 'sub-1' });
    expect(listRevokeRequests).toHaveBeenCalledWith({});
    expect(wrapper.text()).toContain('wrong document');

    await wrapper.find('[data-test="revoke-phase-select"]').setValue('phase-2');
    await wrapper.find('[data-test="revoke-reason"]').setValue('wrong document');
    await wrapper.find('[data-test="submit-revoke-request"]').trigger('click');
    await flushPromises();

    expect(submitRevokeRequest).toHaveBeenCalledWith({
      phaseId: 'phase-2',
      reason: 'wrong document',
    });
  });

  it('lets reviewers approve or reject pending revoke requests', async () => {
    const authStore = useAuthStore();
    authStore.setAccessToken('admin-token');
    authStore.setUser({
      deptId: null,
      email: null,
      id: 'admin-1',
      role: 'admin',
      status: 'active',
      username: 'admin',
    });
    const wrapper = mount(RevokeReview, { global: { stubs } });
    await flushPromises();

    expect(listRevokeRequests).toHaveBeenCalledWith({ status: 'pending' });
    expect(wrapper.text()).toContain('wrong document');

    await wrapper.find('[data-test="revoke-review-comment"]').setValue('ok');
    await wrapper.find('[data-test="approve-revoke-request"]').trigger('click');
    await flushPromises();

    expect(reviewRevokeRequest).toHaveBeenCalledWith('revoke-1', {
      decision: 'approve',
      reviewComment: 'ok',
    });

    await wrapper.find('[data-test="reject-revoke-request"]').trigger('click');
    await flushPromises();

    expect(reviewRevokeRequest).toHaveBeenLastCalledWith('revoke-1', {
      decision: 'reject',
      reviewComment: 'ok',
    });
  });
});

const completedPhase: PhaseRead = {
  code: 'contract',
  created_at: '2026-05-10T00:00:00Z',
  enter_at: '2026-05-10T00:00:00Z',
  finish_at: '2026-05-11T00:00:00Z',
  id: 'phase-2',
  name: '合同',
  phase_no: 2,
  procurement_type: null,
  status: 'completed',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-11T00:00:00Z',
};

const activePhase: PhaseRead = {
  ...completedPhase,
  finish_at: null,
  id: 'phase-3',
  name: '执行',
  phase_no: 3,
  status: 'in_progress',
};

const pendingRequest: RevokeRequestRead = {
  created_at: '2026-05-10T00:00:00Z',
  id: 'revoke-1',
  phase_id: 'phase-2',
  reason: 'wrong document',
  requester_id: 'leader-1',
  review_comment: null,
  reviewed_at: null,
  reviewer_id: null,
  status: 'pending',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T00:00:00Z',
};

const approvedRequest: RevokeRequestRead = {
  ...pendingRequest,
  review_comment: 'ok',
  reviewed_at: '2026-05-11T00:00:00Z',
  reviewer_id: 'admin-1',
  status: 'approved',
};

const stubs = {
  ElAlert: { props: ['title'], template: '<section>{{ title }}</section>' },
  ElButton: {
    emits: ['click'],
    props: ['disabled', 'loading', 'type'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
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
