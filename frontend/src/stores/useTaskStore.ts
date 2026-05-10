import { defineStore } from 'pinia';

import {
  completeTask as completeTaskRequest,
  createTask as createTaskRequest,
  getTask,
  listTasks,
  updateTask as updateTaskRequest,
} from '@/api/tasks';
import type { TaskCreatePayload, TaskListQuery, TaskRead, TaskUpdatePayload } from '@/types/tasks';

interface TaskState {
  currentTask: TaskRead | null;
  detailLoading: boolean;
  listQuery: TaskListQuery;
  loading: boolean;
  tasks: TaskRead[];
  total: number;
}

export const useTaskStore = defineStore('tasks', {
  state: (): TaskState => ({
    currentTask: null,
    detailLoading: false,
    listQuery: {},
    loading: false,
    tasks: [],
    total: 0,
  }),
  actions: {
    async fetchTasks(query?: TaskListQuery) {
      const nextQuery = query ?? this.listQuery;
      this.loading = true;
      this.listQuery = nextQuery;
      try {
        const result = await listTasks(nextQuery);
        this.tasks = result.items;
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async fetchTaskDetail(taskId: string) {
      this.detailLoading = true;
      try {
        const task = await getTask(taskId);
        this.currentTask = task;
        this.upsertTask(task);
        return task;
      } finally {
        this.detailLoading = false;
      }
    },
    async createTask(payload: TaskCreatePayload) {
      const task = await createTaskRequest(payload);
      this.currentTask = task;
      this.upsertTask(task);
      return task;
    },
    async updateTask(taskId: string, payload: TaskUpdatePayload) {
      const task = await updateTaskRequest(taskId, payload);
      this.currentTask = task;
      this.upsertTask(task);
      return task;
    },
    async completeTask(taskId: string) {
      const task = await completeTaskRequest(taskId);
      this.currentTask = task;
      this.upsertTask(task);
      return task;
    },
    upsertTask(task: TaskRead) {
      const existingIndex = this.tasks.findIndex((item) => item.id === task.id);
      if (existingIndex >= 0) {
        this.tasks.splice(existingIndex, 1, task);
        return;
      }
      this.tasks = [task, ...this.tasks];
      this.total = Math.max(this.total, this.tasks.length);
    },
  },
});
