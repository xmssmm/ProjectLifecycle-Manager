import { setActivePinia, createPinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useAuthStore } from '../src/stores/useAuthStore';

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('stores and clears the access token', () => {
    const store = useAuthStore();

    store.setAccessToken('token-value');
    expect(store.accessToken).toBe('token-value');

    store.setAccessToken(null);
    expect(store.accessToken).toBeNull();
  });
});
