import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import { completeTask, createTask, getTask, listTasks, updateTask } from '../src/api/tasks';

describe('tasks api', () => {
  it('supports task list, create, update, detail, and complete endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: { items: [sampleTask], total: 1 },
    });

    await listTasks(
      {
        assignee: 'me',
        status: 'in_progress',
        subProjectId: 'sub-1',
      },
      client,
    );

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleTask,
    });
    await createTask(
      {
        executors: [{ plan_end_date: '2026-05-20', user_id: 'member-1' }],
        name: 'Prepare minutes',
        phase_id: 'phase-1',
        plan_end_date: '2026-05-22',
        sub_project_id: 'sub-1',
      },
      client,
    );
    await getTask('task-1', client);
    await updateTask('task-1', { name: 'Updated' }, client);
    await completeTask('task-1', client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: {
        assignee: 'me',
        status: 'in_progress',
        sub_project_id: 'sub-1',
      },
      url: '/tasks',
    });
    expect(calls[1]).toMatchObject({ method: 'post', url: '/tasks' });
    expect(calls[2]).toMatchObject({ method: 'get', url: '/tasks/task-1' });
    expect(calls[3]).toMatchObject({ method: 'put', url: '/tasks/task-1' });
    expect(calls[4]).toMatchObject({ method: 'post', url: '/tasks/task-1/complete' });
  });
});

const sampleTask = {
  created_at: '2026-05-10T00:00:00Z',
  executors: [
    {
      actual_end_date: null,
      created_at: '2026-05-10T00:00:00Z',
      id: 'executor-1',
      plan_end_date: '2026-05-20',
      status: 'in_progress',
      task_id: 'task-1',
      updated_at: '2026-05-10T00:00:00Z',
      user_id: 'member-1',
    },
  ],
  id: 'task-1',
  name: 'Prepare minutes',
  phase_id: 'phase-1',
  plan_end_date: '2026-05-22',
  status: 'in_progress',
  sub_project_id: 'sub-1',
  task_no: 'Z-2026-0001-ZX-001-T-001',
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
