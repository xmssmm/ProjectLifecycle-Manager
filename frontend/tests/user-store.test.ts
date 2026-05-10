import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  batchHandoverSubProjects,
  createUser,
  disableUser,
  listActiveSubProjectsForLeader,
  listSubProjectHandovers,
  listUsers,
  resetUserPassword,
  updateUser,
} from '@/api/users';

import { useUserStore } from '../src/stores/useUserStore';

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

  it('loads active sub projects and batches handover', async () => {
    const store = useUserStore();

    await store.fetchActiveSubProjectsForLeader('leader-1');
    const result = await store.batchHandoverSubProjects('leader-1', [
      {
        reason: '负责人离职',
        sub_project_id: 'sub-1',
        to_user_id: 'leader-2',
      },
    ]);

    expect(listActiveSubProjectsForLeader).toHaveBeenCalledWith('leader-1');
    expect(batchHandoverSubProjects).toHaveBeenCalledWith('leader-1', [
      {
        reason: '负责人离职',
        sub_project_id: 'sub-1',
        to_user_id: 'leader-2',
      },
    ]);
    expect(store.activeSubProjects).toHaveLength(0);
    expect(result.items[0].manager_id).toBe('leader-2');
  });

  it('loads handover history with filters', async () => {
    const store = useUserStore();

    await store.fetchSubProjectHandovers({ fromUserId: 'leader-1', page: 1, pageSize: 20 });

    expect(listSubProjectHandovers).toHaveBeenCalledWith({
      fromUserId: 'leader-1',
      page: 1,
      pageSize: 20,
    });
    expect(store.handoverHistory[0].reason).toBe('负责人离职');
    expect(store.handoverHistoryTotal).toBe(1);
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
