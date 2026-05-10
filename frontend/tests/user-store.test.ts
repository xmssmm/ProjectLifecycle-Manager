import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createUser, disableUser, listUsers, resetUserPassword, updateUser } from '@/api/users';

import { useUserStore } from '../src/stores/useUserStore';

vi.mock('@/api/users', () => ({
  createUser: vi.fn(),
  disableUser: vi.fn(),
  listUsers: vi.fn(),
  resetUserPassword: vi.fn(),
  updateUser: vi.fn(),
}));

describe('useUserStore', () => {
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

  it('loads users and stores pagination state', async () => {
    const store = useUserStore();

    await store.fetchUsers({ page: 1, pageSize: 20, role: 'admin' });

    expect(listUsers).toHaveBeenCalledWith({ page: 1, pageSize: 20, role: 'admin' });
    expect(store.users[0].username).toBe('admin');
    expect(store.total).toBe(1);
  });

  it('refreshes the current list after user mutations', async () => {
    vi.mocked(createUser).mockResolvedValue(sampleUser);
    vi.mocked(updateUser).mockResolvedValue(sampleUser);
    vi.mocked(disableUser).mockResolvedValue({ ...sampleUser, status: 'disabled' });
    vi.mocked(resetUserPassword).mockResolvedValue({
      ...sampleUser,
      status: 'password_reset_required',
    });
    vi.mocked(listUsers).mockResolvedValue({
      items: [sampleUser],
      page: 2,
      page_size: 50,
      total: 1,
    });
    const store = useUserStore();
    await store.fetchUsers({ page: 2, pageSize: 50, role: 'admin' });

    await store.createUser({
      dept_id: null,
      email: 'admin@example.com',
      password: 'ChangeMe123!',
      role: 'admin',
      username: 'admin',
    });
    await store.updateUser('user-1', { email: 'next@example.com' });
    await store.disableUser('user-1');
    await store.resetPassword('user-1', { new_password: 'NextPass123!' });

    expect(listUsers).toHaveBeenLastCalledWith({ page: 2, pageSize: 50, role: 'admin' });
    expect(listUsers).toHaveBeenCalledTimes(5);
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
