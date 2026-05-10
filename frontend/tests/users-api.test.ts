import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  batchHandoverSubProjects,
  createUser,
  changeOwnPassword,
  disableUser,
  getUser,
  listActiveSubProjectsForLeader,
  listSubProjectHandovers,
  listUsers,
  resetUserPassword,
  updateUser,
} from '../src/api/users';

describe('users api', () => {
  it('lists users with pagination and role filters', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: {
        items: [sampleUser],
        page: 2,
        page_size: 50,
        total: 1,
      },
    });

    const result = await listUsers({ page: 2, pageSize: 50, role: 'admin' }, client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { page: 2, page_size: 50, role: 'admin' },
      url: '/users',
    });
    expect(result.items[0].username).toBe('admin');
  });

  it('creates, updates, disables, and resets a user', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleUser,
    });

    await createUser(
      {
        dept_id: null,
        email: 'admin@example.com',
        password: 'ChangeMe123!',
        role: 'admin',
        username: 'admin',
      },
      client,
    );
    await updateUser('user-1', { email: 'next@example.com' }, client);
    await updateUser('user-1', { sso_required: true }, client);
    await disableUser('user-1', client);
    await resetUserPassword('user-1', { new_password: 'NextPass123!' }, client);
    await changeOwnPassword({ new_password: 'NextPass123!', old_password: 'OldPass123!' }, client);

    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      'post /users',
      'put /users/user-1',
      'put /users/user-1',
      'delete /users/user-1',
      'post /users/user-1/reset-password',
      'post /users/me/change-password',
    ]);
    expect(calls[2]).toMatchObject({
      data: JSON.stringify({ sso_required: true }),
      method: 'put',
      url: '/users/user-1',
    });
  });

  it('gets a single user profile', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleUser,
    });

    const result = await getUser('user-1', client);

    expect(calls[0]).toMatchObject({ method: 'get', url: '/users/user-1' });
    expect(result.email).toBe('admin@example.com');
  });

  it('supports project handover endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: {
        items: [sampleHandover],
        page: 1,
        page_size: 20,
        total: 1,
      },
    });

    await listSubProjectHandovers({ fromUserId: 'leader-1', page: 1, pageSize: 20 }, client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: {
        items: [sampleSubProject],
        page: 1,
        page_size: 1,
        total: 1,
      },
    });

    await listActiveSubProjectsForLeader('leader-1', client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: {
        items: [{ ...sampleSubProject, manager_id: 'leader-2' }],
        total: 1,
      },
    });
    await batchHandoverSubProjects(
      'leader-1',
      [
        {
          reason: '负责人离职',
          sub_project_id: 'sub-1',
          to_user_id: 'leader-2',
        },
      ],
      client,
    );

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: {
        from_user_id: 'leader-1',
        page: 1,
        page_size: 20,
        sub_project_id: undefined,
        to_user_id: undefined,
      },
      url: '/users/handovers',
    });
    expect(calls[1]).toMatchObject({
      method: 'get',
      url: '/users/leader-1/active-sub-projects',
    });
    expect(calls[2]).toMatchObject({
      data: JSON.stringify([
        {
          reason: '负责人离职',
          sub_project_id: 'sub-1',
          to_user_id: 'leader-2',
        },
      ]),
      method: 'post',
      url: '/users/leader-1/batch-handover',
    });
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
  sso_required: false,
  status: 'active',
  updated_at: '2026-05-10T00:00:00Z',
  username: 'admin',
};

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
};

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
};

function recordingAdapter(calls: AxiosRequestConfig[], data: unknown): AxiosAdapter {
  return async (config) => {
    calls.push(config);
    return {
      config,
      data,
      headers: {},
      status: 200,
      statusText: 'OK',
    };
  };
}
