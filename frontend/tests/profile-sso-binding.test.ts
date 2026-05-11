import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getCurrentUser } from '@/api/auth';
import { listNotificationPreferences, updateNotificationPreferences } from '@/api/notifications';
import {
  listOAuthBindings,
  listOAuthProviders,
  unbindOAuthProvider,
} from '@/api/oauth';
import { getUser, updateUser } from '@/api/users';
import { useAuthStore } from '@/stores/useAuthStore';
import Profile from '@/views/Profile.vue';

vi.mock('@/api/auth', () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

vi.mock('@/api/users', () => ({
  getUser: vi.fn(),
  updateUser: vi.fn(),
}));

vi.mock('@/api/notifications', () => ({
  listNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}));

vi.mock('@/api/oauth', () => ({
  listOAuthBindings: vi.fn(),
  listOAuthProviders: vi.fn(),
  startOAuthLogin: vi.fn(),
  unbindOAuthProvider: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}));

describe('Profile OAuth SSO bindings', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(getCurrentUser).mockResolvedValue(sampleCurrentUser);
    vi.mocked(getUser).mockResolvedValue(sampleUser);
    vi.mocked(updateUser).mockResolvedValue(sampleUser);
    vi.mocked(listNotificationPreferences).mockResolvedValue({ items: [] });
    vi.mocked(updateNotificationPreferences).mockResolvedValue({ items: [] });
    vi.mocked(listOAuthProviders).mockResolvedValue([
      { label: '企业账号', provider: 'generic_oidc' },
    ]);
    vi.mocked(listOAuthBindings).mockResolvedValue([sampleBinding]);
    vi.mocked(unbindOAuthProvider).mockResolvedValue({ unbound: true });

    const authStore = useAuthStore();
    authStore.setAccessToken('token');
    authStore.setUser({
      deptId: null,
      email: 'admin@example.local',
      id: 'user-1',
      role: 'admin',
      status: 'active',
      username: 'admin',
    });
  });

  it('shows OAuth binding status and unbinds a provider', async () => {
    const wrapper = mount(Profile, { global: { stubs } });
    await flushPromises();

    expect(listOAuthProviders).toHaveBeenCalled();
    expect(listOAuthBindings).toHaveBeenCalled();
    expect(wrapper.find('[data-test="oauth-binding-generic_oidc"]').text()).toContain('已绑定');

    const bindingLoadCount = vi.mocked(listOAuthBindings).mock.calls.length;
    await wrapper.find('[data-test="oauth-unbind-generic_oidc"]').trigger('click');
    await flushPromises();

    expect(unbindOAuthProvider).toHaveBeenCalledWith('generic_oidc');
    expect(vi.mocked(listOAuthBindings).mock.calls.length).toBeGreaterThan(bindingLoadCount);
  });
});

const sampleCurrentUser = {
  dept_id: null,
  email: 'admin@example.local',
  id: 'user-1',
  role: 'admin',
  status: 'active',
  timezone: 'Asia/Shanghai',
  username: 'admin',
} as const;

const sampleUser = {
  created_at: '2026-05-10T00:00:00Z',
  dept_id: null,
  email: 'admin@example.local',
  id: 'user-1',
  last_login_at: null,
  password_changed_at: '2026-05-10T00:00:00Z',
  role: 'admin',
  sso_required: false,
  status: 'active',
  timezone: 'Asia/Shanghai',
  updated_at: '2026-05-10T00:00:00Z',
  username: 'admin',
} as const;

const sampleBinding = {
  created_at: '2026-05-10T00:00:00Z',
  email: 'admin@example.local',
  expires_at: null,
  external_id: 'external-user-1',
  id: 'binding-1',
  provider: 'generic_oidc',
  updated_at: '2026-05-10T00:00:00Z',
  user_id: 'user-1',
} as const;

const stubs = {
  ElButton: {
    props: ['disabled', 'loading'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
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
