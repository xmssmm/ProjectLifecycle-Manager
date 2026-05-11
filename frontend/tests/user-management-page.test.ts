import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listUsers } from '@/api/users';
import UserList from '@/views/admin/UserList.vue';

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

describe('UserList', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listUsers).mockResolvedValue({
      items: [sampleUser],
      page: 1,
      page_size: 20,
      total: 1,
    });
  });

  it('loads and renders the user table with admin actions', async () => {
    const wrapper = mount(UserList, { global: { stubs } });
    await flushPromises();

    expect(listUsers).toHaveBeenCalledWith({ page: 1, pageSize: 20, role: undefined });
    expect(wrapper.text()).toContain('admin');
    expect(wrapper.text()).toContain('仅 SSO');
    expect(wrapper.text()).toContain('系统会在停用前检查在途项目');
    expect(wrapper.find('[data-test="edit-user"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="disable-user"]').exists()).toBe(true);
  });

  it('opens the create user dialog', async () => {
    const wrapper = mount(UserList, { global: { stubs } });
    await flushPromises();

    await wrapper.find('[data-test="create-user"]').trigger('click');

    expect(wrapper.find('[data-test="user-edit-dialog"]').exists()).toBe(true);
  });
});

const sampleUser = {
  created_at: '2026-05-10T00:00:00Z',
  dept_id: null,
  email: 'admin@example.com',
  id: 'user-1',
  last_login_at: null,
  password_changed_at: '2026-05-10T00:00:00Z',
  role: 'admin',
  sso_required: true,
  status: 'active',
  timezone: 'Asia/Shanghai',
  updated_at: '2026-05-10T00:00:00Z',
  username: 'admin',
} as const;

const stubs = {
  ConfirmDialog: {
    props: ['modelValue', 'message', 'title'],
    template: '<section v-if="modelValue">{{ title }}{{ message }}<slot /></section>',
  },
  DataTable: {
    props: ['columns', 'loading', 'page', 'pageSize', 'rows', 'total'],
    template:
      '<section><article v-for="row in rows" :key="row.id"><span>{{ row.username }}</span><slot name="role" :row="row" :value="row.role" /><slot name="status" :row="row" :value="row.status" /><slot name="sso_required" :row="row" :value="row.sso_required" /><slot name="actions" :row="row" /></article></section>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: {
    props: ['modelValue'],
    template: '<section v-if="modelValue"><slot /><slot name="footer" /></section>',
  },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElOption: { template: '<option><slot /></option>' },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
  ElTooltip: { template: '<span><slot />{{ content }}</span>', props: ['content'] },
  SearchBar: { template: '<section><slot /></section>' },
  StatusTag: { props: ['status'], template: '<span>{{ status }}</span>' },
  UserEdit: {
    props: ['modelValue'],
    template: '<section v-if="modelValue" data-test="user-edit-dialog"></section>',
  },
};
