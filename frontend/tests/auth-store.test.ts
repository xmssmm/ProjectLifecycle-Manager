import { setActivePinia, createPinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApp, nextTick } from 'vue';

import { getCurrentUser, login, logout, refreshAccessToken } from '@/api/auth';

import { createAppPinia } from '../src/stores';
import { useAuthStore } from '../src/stores/useAuthStore';

vi.mock('@/api/auth', () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('stores and clears the access token', () => {
    const store = useAuthStore();

    store.setAccessToken('token-value');
    expect(store.accessToken).toBe('token-value');

    store.setAccessToken(null);
    expect(store.accessToken).toBeNull();
  });

  it('persists the access token in the app pinia instance', async () => {
    const pinia = createAppPinia();
    createApp({}).use(pinia);
    setActivePinia(pinia);
    const store = useAuthStore();

    store.setAccessToken('persisted-token');
    await nextTick();

    expect(localStorage.getItem('project-mgmt-auth')).toContain('persisted-token');
  });

  it('logs in and loads the current user', async () => {
    vi.mocked(login).mockResolvedValue({
      access_token: 'access-token',
      refresh_token: 'refresh-token',
      token_type: 'bearer',
    });
    vi.mocked(getCurrentUser).mockResolvedValue({
      dept_id: null,
      email: 'admin@example.com',
      id: 'user-1',
      role: 'admin',
      status: 'active',
      username: 'admin',
    });
    const store = useAuthStore();

    await store.login('admin', 'StrongPass1!');

    expect(store.accessToken).toBe('access-token');
    expect(store.user).toMatchObject({
      email: 'admin@example.com',
      status: 'active',
      username: 'admin',
    });
  });

  it('refreshes and clears the session on logout', async () => {
    vi.mocked(refreshAccessToken).mockResolvedValue({
      access_token: 'fresh-token',
      token_type: 'bearer',
    });
    vi.mocked(logout).mockResolvedValue(undefined);
    const store = useAuthStore();
    store.setAccessToken('old-token');
    store.setUser({
      deptId: null,
      email: 'admin@example.com',
      id: 'user-1',
      role: 'admin',
      status: 'active',
      username: 'admin',
    });

    await store.refreshSession();
    expect(store.accessToken).toBe('fresh-token');

    await store.logout();
    expect(store.accessToken).toBeNull();
    expect(store.user).toBeNull();
  });
});
