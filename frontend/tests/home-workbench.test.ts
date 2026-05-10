import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listTasks } from '@/api/tasks';
import type { TaskRead } from '@/types/tasks';
import HomeView from '@/views/HomeView.vue';

vi.mock('@/api/tasks', () => ({
  completeTask: vi.fn(),
  createTask: vi.fn(),
  getTask: vi.fn(),
  listTasks: vi.fn(),
  updateTask: vi.fn(),
}));

describe('HomeView task workbench', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads my unfinished tasks and sorts them by due date', async () => {
    vi.mocked(listTasks).mockResolvedValue({
      items: [laterTask, completedTask, earlierTask],
      total: 3,
    });

    const wrapper = mount(HomeView, { global: { stubs } });
    await flushPromises();

    expect(listTasks).toHaveBeenCalledWith({ assignee: 'me' });
    const rows = wrapper.findAll('[data-test="workbench-task-row"]');
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain('Due first');
    expect(rows[1].text()).toContain('Due later');
    expect(wrapper.text()).not.toContain('Already done');
    expect(wrapper.find('[data-test="task-detail-link"]').attributes('to')).toContain('task-early');
  });
});

const baseTask: TaskRead = {
  created_at: '2026-05-10T00:00:00Z',
  executors: [
    {
      actual_end_date: null,
      created_at: '2026-05-10T00:00:00Z',
      id: 'executor-1',
      plan_end_date: '2026-05-20',
      status: 'in_progress',
      task_id: 'task-base',
      updated_at: '2026-05-10T00:00:00Z',
      user_id: 'member-1',
    },
  ],
  id: 'task-base',
  name: 'Base task',
  phase_id: 'phase-1',
  plan_end_date: '2026-05-20',
  status: 'in_progress',
  sub_project_id: 'sub-1',
  task_no: 'TASK-BASE',
  updated_at: '2026-05-10T00:00:00Z',
};

const laterTask: TaskRead = {
  ...baseTask,
  id: 'task-later',
  name: 'Due later',
  plan_end_date: '2026-05-22',
  task_no: 'TASK-LATER',
};

const earlierTask: TaskRead = {
  ...baseTask,
  id: 'task-early',
  name: 'Due first',
  plan_end_date: '2026-05-11',
  task_no: 'TASK-EARLY',
};

const completedTask: TaskRead = {
  ...baseTask,
  id: 'task-done',
  name: 'Already done',
  status: 'completed',
  task_no: 'TASK-DONE',
};

const stubs = {
  ElButton: { template: '<button><slot /></button>' },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  RouterLink: {
    props: ['to'],
    template:
      "<a :to=\"typeof to === 'string' ? to : `${to.name}:${to.params?.id ?? ''}`\"><slot /></a>",
  },
};
