import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { changeOwnPassword, getUser, updateUser } from '@/api/users';
import ChangePassword from '@/views/ChangePassword.vue';
import Profile from '@/views/Profile.vue';
import { useAuthStore } from '@/stores/useAuthStore';

vi.mock('@/api/auth', () => ({
  getCurrentUser: vi.fn().mockResolvedValue({
    dept_id: null,
    email: 'next@example.com',
    id: 'user-1',
    role: 'admin',
    status: 'active',
    username: 'admin',
  }),
  login: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

vi.mock('@/api/users', () => ({
  changeOwnPassword: vi.fn(),
  getUser: vi.fn(),
  updateUser: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

describe('profile and password pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(getUser).mockResolvedValue(sampleUser);
    vi.mocked(updateUser).mockResolvedValue(sampleUser);
    vi.mocked(changeOwnPassword).mockResolvedValue(sampleUser);
    const authStore = useAuthStore();
    authStore.setAccessToken('token');
    authStore.setUser({
      deptId: null,
      email: 'admin@example.com',
      id: 'user-1',
      role: 'admin',
      status: 'active',
      username: 'admin',
    });
  });

  it('loads the current user profile and saves email changes', async () => {
    const wrapper = mount(Profile, { global: { stubs } });
    await flushPromises();

    expect(getUser).toHaveBeenCalledWith('user-1');
    await wrapper.find('[data-test="profile-email"] input').setValue('next@example.com');
    await wrapper.find('[data-test="profile-save"]').trigger('click');
    await flushPromises();

    expect(updateUser).toHaveBeenCalledWith('user-1', { email: 'next@example.com' });
  });

  it('validates confirmation before changing password', async () => {
    const wrapper = mount(ChangePassword, { global: { stubs } });

    await wrapper.find('[data-test="old-password"] input').setValue('OldPass123!');
    await wrapper.find('[data-test="new-password"] input').setValue('NewPass123!');
    await wrapper.find('[data-test="confirm-password"] input').setValue('Different123!');
    await wrapper.find('[data-test="password-save"]').trigger('click');

    expect(wrapper.text()).toContain('两次输入的新密码不一致');
    expect(changeOwnPassword).not.toHaveBeenCalled();
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
  status: 'active',
  updated_at: '2026-05-10T00:00:00Z',
  username: 'admin',
} as const;

const stubs = {
  ElAlert: { props: ['title'], template: '<section>{{ title }}<slot /></section>' },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDescriptions: { template: '<dl><slot /></dl>' },
  ElDescriptionsItem: { template: '<dd><slot /></dd>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<span><input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /></span>',
  },
};
