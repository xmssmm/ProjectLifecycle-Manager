import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { changeOwnPassword, getUser, updateUser } from '@/api/users';
import ChangePassword from '@/views/ChangePassword.vue';
import Profile from '@/views/Profile.vue';
import { useAuthStore } from '@/stores/useAuthStore';
import { listNotificationPreferences, updateNotificationPreferences } from '@/api/notifications';

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

vi.mock('@/api/notifications', () => ({
  listNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
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
    vi.mocked(listNotificationPreferences).mockResolvedValue({
      items: [taskPreference, overduePreference],
    });
    vi.mocked(updateNotificationPreferences).mockResolvedValue({
      items: [{ ...taskPreference, enabled: false }, overduePreference],
    });
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

  it('loads and saves notification preferences from the profile page', async () => {
    const wrapper = mount(Profile, { global: { stubs } });
    await flushPromises();

    expect(listNotificationPreferences).toHaveBeenCalled();
    expect(wrapper.find('[data-test="notification-preference-task_assigned"]').exists()).toBe(
      true,
    );

    await wrapper
      .find('[data-test="notification-preference-task_assigned"] input')
      .setValue(false);
    await wrapper.find('[data-test="notification-preferences-save"]').trigger('click');
    await flushPromises();

    expect(updateNotificationPreferences).toHaveBeenCalledWith({
      preferences: [
        { delivery_mode: 'real_time', enabled: false, scenario: 'task_assigned' },
        {
          delivery_mode: 'daily_digest',
          enabled: false,
          scenario: 'task_overdue_escalation',
        },
      ],
    });
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

const taskPreference = {
  description: '任务执行人收到任务分配提醒',
  direct_related: true,
  delivery_mode: 'real_time',
  enabled: true,
  label: '任务分配',
  scenario: 'task_assigned',
} as const;

const overduePreference = {
  description: '项目管理人员收到逾期升级提醒',
  direct_related: false,
  delivery_mode: 'daily_digest',
  enabled: false,
  label: '逾期升级',
  scenario: 'task_overdue_escalation',
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
  ElRadioButton: {
    props: ['label', 'value'],
    template: '<button type="button" @click="$emit(\'change\', value ?? label)"><slot /></button>',
  },
  ElRadioGroup: {
    props: ['modelValue'],
    template: '<div><slot /></div>',
  },
  ElSwitch: {
    props: ['modelValue'],
    template:
      '<span><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" /></span>',
  },
};
