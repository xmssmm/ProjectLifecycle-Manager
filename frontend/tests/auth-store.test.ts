import { setActivePinia, createPinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';
import { createApp, nextTick } from 'vue';

import { createAppPinia } from '../src/stores';
import { useAuthStore } from '../src/stores/useAuthStore';

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
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
});
