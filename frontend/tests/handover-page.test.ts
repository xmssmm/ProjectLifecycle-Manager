import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  batchHandoverSubProjects,
  listActiveSubProjectsForLeader,
  listSubProjectHandovers,
  listUsers,
} from '@/api/users';
import HandoverHistory from '@/views/admin/HandoverHistory.vue';
import UserHandover from '@/views/admin/UserHandover.vue';

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
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
};
