import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { completeTask, createTask, getTask, listTasks } from '@/api/tasks';
import { useTaskStore } from '@/stores/useTaskStore';
import type { TaskRead } from '@/types/tasks';

vi.mock('@/api/tasks', () => ({
  completeTask: vi.fn(),
  createTask: vi.fn(),
  getTask: vi.fn(),
  listTasks: vi.fn(),
  updateTask: vi.fn(),
}));

describe('task store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads tasks and keeps current detail in sync after create and complete', async () => {
    vi.mocked(listTasks).mockResolvedValue({ items: [sampleTask], total: 1 });
    vi.mocked(getTask).mockResolvedValue(sampleTask);
    vi.mocked(createTask).mockResolvedValue(sampleTask);
    vi.mocked(completeTask).mockResolvedValue({ ...sampleTask, status: 'completed' });
    const store = useTaskStore();

    await store.fetchTasks({ assignee: 'me', status: 'in_progress', subProjectId: 'sub-1' });
    await store.fetchTaskDetail('task-1');
    await store.createTask({
      executors: [{ plan_end_date: '2026-05-20', user_id: 'member-1' }],
      name: 'Prepare minutes',
      phase_id: 'phase-1',
      plan_end_date: '2026-05-22',
      sub_project_id: 'sub-1',
    });
    await store.completeTask('task-1');

    expect(listTasks).toHaveBeenCalledWith({
      assignee: 'me',
      status: 'in_progress',
      subProjectId: 'sub-1',
    });
    expect(store.tasks).toHaveLength(1);
    expect(store.currentTask?.status).toBe('completed');
    expect(store.tasks[0].status).toBe('completed');
  });
});

const sampleTask: TaskRead = {
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
