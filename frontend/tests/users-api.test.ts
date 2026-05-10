import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  createUser,
  disableUser,
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
    await disableUser('user-1', client);
    await resetUserPassword('user-1', { new_password: 'NextPass123!' }, client);

    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      'post /users',
      'put /users/user-1',
      'delete /users/user-1',
      'post /users/user-1/reset-password',
    ]);
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
