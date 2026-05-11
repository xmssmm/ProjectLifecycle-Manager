import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getCurrentUser } from '@/api/auth';
import {
  completeOAuthCallback,
  listOAuthProviders,
  startOAuthLogin,
} from '@/api/oauth';
import LoginView from '@/views/auth/LoginView.vue';

const routerReplace = vi.fn();
let routeQuery: Record<string, string> = {};

vi.mock('@/api/auth', () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

vi.mock('@/api/oauth', () => ({
  completeOAuthCallback: vi.fn(),
  listOAuthProviders: vi.fn(),
  startOAuthLogin: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ replace: routerReplace }),
}));

describe('LoginView OAuth SSO', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    routeQuery = {};
    vi.mocked(listOAuthProviders).mockResolvedValue([
      { label: '企业账号', provider: 'generic_oidc' },
    ]);
    vi.mocked(getCurrentUser).mockResolvedValue({
      dept_id: null,
      email: 'admin@example.local',
      id: 'user-1',
      role: 'admin',
      status: 'active',
      timezone: 'Asia/Shanghai',
      username: 'admin',
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders enterprise login providers and starts OAuth login', async () => {
    vi.mocked(startOAuthLogin).mockResolvedValue({
      authorization_url: 'https://sso.example.local/authorize?state=state-1',
      state: 'state-1',
    });
    const assign = vi.fn();
    vi.stubGlobal('location', { assign });

    const wrapper = mount(LoginView, { global: { stubs } });
    await flushPromises();

    expect(wrapper.text()).toContain('企业账号登录');
    await wrapper.find('[data-test="oauth-login-generic_oidc"]').trigger('click');
    await flushPromises();

    expect(startOAuthLogin).toHaveBeenCalledWith('generic_oidc');
    expect(assign).toHaveBeenCalledWith('https://sso.example.local/authorize?state=state-1');
  });

  it('completes OAuth callback and stores the issued token', async () => {
    routeQuery = {
      code: 'code-1',
      oauth_provider: 'generic_oidc',
      redirect: '/tasks',
      state: 'state-1',
    };
    vi.mocked(completeOAuthCallback).mockResolvedValue({
      access_token: 'oauth-access-token',
      refresh_token: 'oauth-refresh-token',
      token_type: 'bearer',
    });

    mount(LoginView, { global: { stubs } });
    await flushPromises();

    expect(completeOAuthCallback).toHaveBeenCalledWith({
      code: 'code-1',
      provider: 'generic_oidc',
      state: 'state-1',
    });
    expect(routerReplace).toHaveBeenCalledWith('/tasks');
  });
});

const stubs = {
  ElButton: {
    props: ['disabled', 'loading'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElCheckbox: {
    props: ['modelValue'],
    template:
      '<label><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" /><slot /></label>',
  },
  ElDivider: { template: '<div><slot /></div>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<span><input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /></span>',
  },
};
