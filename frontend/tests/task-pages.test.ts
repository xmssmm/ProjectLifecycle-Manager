import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { completeTask, createTask, getTask, listTasks } from '@/api/tasks';
import { useAuthStore } from '@/stores/useAuthStore';
import type { TaskRead } from '@/types/tasks';
import TaskDetail from '@/views/task/TaskDetail.vue';
import TaskList from '@/views/task/TaskList.vue';

vi.mock('@/api/tasks', () => ({
  completeTask: vi.fn(),
  createTask: vi.fn(),
  getTask: vi.fn(),
  listTasks: vi.fn(),
  updateTask: vi.fn(),
}));

describe('TaskList', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listTasks).mockResolvedValue({ items: [sampleTask], total: 1 });
    vi.mocked(createTask).mockResolvedValue(sampleTask);
  });

  it('filters by sub project, status, assignee=me and creates assigned tasks', async () => {
    const wrapper = mount(TaskList, { global: { stubs } });
    await flushPromises();

    expect(listTasks).toHaveBeenCalledWith({});
    expect(wrapper.text()).toContain('Prepare minutes');

    await wrapper.find('[data-test="filter-sub-project"]').setValue('sub-1');
    await wrapper.find('[data-test="filter-status"]').setValue('in_progress');
    await wrapper.find('[data-test="filter-assignee-me"]').setValue(true);
    await wrapper.find('[data-test="search-tasks"]').trigger('click');
    await flushPromises();

    expect(listTasks).toHaveBeenLastCalledWith({
      assignee: 'me',
      status: 'in_progress',
      subProjectId: 'sub-1',
    });

    await wrapper.find('[data-test="open-create-task"]').trigger('click');
    await wrapper.find('[data-test="task-name"]').setValue('Prepare minutes');
    await wrapper.find('[data-test="task-sub-project"]').setValue('sub-1');
    await wrapper.find('[data-test="task-phase"]').setValue('phase-1');
    await wrapper.find('[data-test="task-plan-end"]').setValue('2026-05-22');
    await wrapper.find('[data-test="task-executor-ids"]').setValue('member-1, member-2');
    await wrapper.find('[data-test="task-executor-plan-end"]').setValue('2026-05-20');
    await wrapper.find('[data-test="submit-task"]').trigger('click');
    await flushPromises();

    expect(createTask).toHaveBeenCalledWith({
      executors: [
        { plan_end_date: '2026-05-20', user_id: 'member-1' },
        { plan_end_date: '2026-05-20', user_id: 'member-2' },
      ],
      name: 'Prepare minutes',
      phase_id: 'phase-1',
      plan_end_date: '2026-05-22',
      sub_project_id: 'sub-1',
    });
  });
});

describe('TaskDetail', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(getTask).mockResolvedValue(sampleTask);
    vi.mocked(completeTask).mockResolvedValue(completedTask);
  });

  it('shows complete button for current assignee and refreshes status', async () => {
    const authStore = useAuthStore();
    authStore.setAccessToken('token');
    authStore.setUser({
      deptId: null,
      email: null,
      id: 'member-1',
      role: 'proj_member',
      status: 'active',
      username: 'member',
    });
    const wrapper = mount(TaskDetail, {
      global: { stubs },
      props: { taskId: 'task-1' },
    });
    await flushPromises();

    expect(getTask).toHaveBeenCalledWith('task-1');
    expect(wrapper.find('[data-test="complete-task"]').exists()).toBe(true);

    await wrapper.find('[data-test="complete-task"]').trigger('click');
    await flushPromises();

    expect(completeTask).toHaveBeenCalledWith('task-1');
    expect(wrapper.text()).toContain('completed');
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
    {
      actual_end_date: null,
      created_at: '2026-05-10T00:00:00Z',
      id: 'executor-2',
      plan_end_date: '2026-05-21',
      status: 'in_progress',
      task_id: 'task-1',
      updated_at: '2026-05-10T00:00:00Z',
      user_id: 'member-2',
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

const completedTask: TaskRead = {
  ...sampleTask,
  executors: sampleTask.executors.map((executor) =>
    executor.user_id === 'member-1'
      ? { ...executor, actual_end_date: '2026-05-10', status: 'completed' }
      : executor,
  ),
  status: 'completed',
};

const stubs = {
  ElButton: {
    emits: ['click'],
    props: ['disabled', 'loading', 'type'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElCheckbox: {
    props: ['modelValue'],
    template:
      '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
  },
  ElDialog: {
    props: ['modelValue'],
    template: '<section v-if="modelValue"><slot /><slot name="footer" /></section>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElOption: {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElSkeleton: { template: '<section />' },
  ElTable: { props: ['data'], template: '<table><tbody><slot /></tbody></table>' },
  ElTableColumn: { template: '<td><slot /></td>' },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
};
