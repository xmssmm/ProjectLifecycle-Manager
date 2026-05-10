import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  createMainProject,
  getMainProject,
  listMainProjects,
  submitMainProject,
  updateMainProject,
} from '../src/api/mainProjects';
import { listSubProjects } from '../src/api/subProjects';

describe('project api', () => {
  it('lists and gets main projects', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: {
        items: [sampleMainProject],
        page: 2,
        page_size: 50,
        total: 1,
      },
    });

    const result = await listMainProjects({ page: 2, pageSize: 50 }, client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { page: 2, page_size: 50 },
      url: '/main-projects',
    });
    expect(result.items[0].project_no).toBe('Z-2026-0001');

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleMainProject,
    });
    const detail = await getMainProject('main-1', client);

    expect(calls[1]).toMatchObject({ method: 'get', url: '/main-projects/main-1' });
    expect(detail.name).toBe('智慧档案平台');
  });

  it('lists sub projects for detail pages', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: {
        items: [sampleSubProject],
        page: 1,
        page_size: 20,
        total: 1,
      },
    });

    const result = await listSubProjects({ page: 1, pageSize: 20 }, client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { page: 1, page_size: 20 },
      url: '/sub-projects',
    });
    expect(result.items[0].main_project_id).toBe('main-1');
  });

  it('creates, updates, and submits main projects', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleMainProject,
    });

    await createMainProject(
      {
        dept_id: 'dept-a',
        expected_finish_date: '2026-12-31',
        name: '智慧档案平台',
        remark: '一期',
        total_budget: '500000.00',
      },
      client,
    );
    await updateMainProject(
      'main-1',
      {
        expected_finish_date: '2027-01-31',
        name: '智慧档案平台二期',
        remark: null,
        total_budget: '520000.00',
      },
      client,
    );
    await submitMainProject('main-1', client);

    expect(calls[0]).toMatchObject({
      data: JSON.stringify({
        dept_id: 'dept-a',
        expected_finish_date: '2026-12-31',
        name: '智慧档案平台',
        remark: '一期',
        total_budget: '500000.00',
      }),
      method: 'post',
      url: '/main-projects',
    });
    expect(calls[1]).toMatchObject({
      data: JSON.stringify({
        expected_finish_date: '2027-01-31',
        name: '智慧档案平台二期',
        remark: null,
        total_budget: '520000.00',
      }),
      method: 'put',
      url: '/main-projects/main-1',
    });
    expect(calls[2]).toMatchObject({
      method: 'post',
      url: '/main-projects/main-1/submit',
    });
  });
});

const sampleMainProject = {
  created_at: '2026-05-10T00:00:00Z',
  creator_id: 'user-1',
  dept_id: 'dept-a',
  expected_finish_date: '2026-12-31',
  id: 'main-1',
  name: '智慧档案平台',
  project_no: 'Z-2026-0001',
  remark: null,
  spent_amount: '0.00',
  status: 'in_progress',
  total_budget: '500000.00',
  updated_at: '2026-05-10T00:00:00Z',
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
