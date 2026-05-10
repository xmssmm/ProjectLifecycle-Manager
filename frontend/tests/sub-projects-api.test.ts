import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  closeSubProject,
  createSubProject,
  getSubProject,
  listSubProjects,
  reviewSubProject,
  submitSubProject,
  terminateSubProject,
  updateSubProject,
} from '../src/api/subProjects';

describe('sub project api', () => {
  it('supports sub project query and workflow endpoints', async () => {
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

    await listSubProjects({ page: 1, pageSize: 20 }, client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleSubProject,
    });
    await getSubProject('sub-1', client);
    await createSubProject(
      {
        budget: '100000.00',
        dept_id: 'dept-a',
        main_project_id: 'main-1',
        name: '采购实施',
        plan_end_date: '2026-10-31',
        remark: '一期',
      },
      client,
    );
    await updateSubProject('sub-1', { name: '采购实施二期', remark: null }, client);
    await submitSubProject('sub-1', client);
    await reviewSubProject(
      'sub-1',
      {
        confirm_over_budget: true,
        decision: 'approve',
        over_budget_reason: '专项预算已确认',
        review_comment: '通过',
        updates: null,
      },
      client,
    );
    await closeSubProject('sub-1', client);
    await terminateSubProject('sub-1', { reason: '需求取消' }, client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { page: 1, page_size: 20 },
      url: '/sub-projects',
    });
    expect(calls[1]).toMatchObject({ method: 'get', url: '/sub-projects/sub-1' });
    expect(calls[2]).toMatchObject({ method: 'post', url: '/sub-projects' });
    expect(calls[3]).toMatchObject({ method: 'put', url: '/sub-projects/sub-1' });
    expect(calls[4]).toMatchObject({ method: 'post', url: '/sub-projects/sub-1/submit' });
    expect(calls[5]).toMatchObject({
      data: JSON.stringify({
        confirm_over_budget: true,
        decision: 'approve',
        over_budget_reason: '专项预算已确认',
        review_comment: '通过',
        updates: null,
      }),
      method: 'post',
      url: '/sub-projects/sub-1/review',
    });
    expect(calls[6]).toMatchObject({ method: 'post', url: '/sub-projects/sub-1/close' });
    expect(calls[7]).toMatchObject({
      data: JSON.stringify({ reason: '需求取消' }),
      method: 'post',
      url: '/sub-projects/sub-1/terminate',
    });
  });
});

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
  status: 'pending_review',
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
