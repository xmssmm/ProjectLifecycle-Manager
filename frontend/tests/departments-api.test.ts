import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  createDepartment,
  deleteDepartment,
  listDepartments,
  updateDepartment,
} from '../src/api/departments';

describe('departments api', () => {
  it('lists departments', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: [sampleDepartment],
    });

    const result = await listDepartments(client);

    expect(calls[0]).toMatchObject({ method: 'get', url: '/departments' });
    expect(result[0].code).toBe('general');
  });

  it('creates, updates, and deletes departments', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleDepartment,
    });

    await createDepartment({ code: 'general', name: '综合部' }, client);
    await updateDepartment('dept-1', { name: '综合管理部' }, client);
    await deleteDepartment('dept-1', client);

    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      'post /departments',
      'put /departments/dept-1',
      'delete /departments/dept-1',
    ]);
  });
});

const sampleDepartment = {
  code: 'general',
  created_at: '2026-05-10T00:00:00Z',
  id: 'dept-1',
  name: '综合部',
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
