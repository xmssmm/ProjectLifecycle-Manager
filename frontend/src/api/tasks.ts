import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  TaskCreatePayload,
  TaskListQuery,
  TaskListRead,
  TaskRead,
  TaskUpdatePayload,
} from '@/types/tasks';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listTasks(
  query: TaskListQuery = {},
  client: AxiosInstance = apiClient,
): Promise<TaskListRead> {
  const response = await client.get<ApiResponse<TaskListRead>>('/tasks', {
    params: {
      assignee: query.assignee,
      status: query.status,
      sub_project_id: query.subProjectId,
    },
  });
  return response.data.data;
}

export async function createTask(
  payload: TaskCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<TaskRead> {
  const response = await client.post<ApiResponse<TaskRead>>('/tasks', payload);
  return response.data.data;
}

export async function getTask(
  taskId: string,
  client: AxiosInstance = apiClient,
): Promise<TaskRead> {
  const response = await client.get<ApiResponse<TaskRead>>(`/tasks/${taskId}`);
  return response.data.data;
}

export async function updateTask(
  taskId: string,
  payload: TaskUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<TaskRead> {
  const response = await client.put<ApiResponse<TaskRead>>(`/tasks/${taskId}`, payload);
  return response.data.data;
}

export async function completeTask(
  taskId: string,
  client: AxiosInstance = apiClient,
): Promise<TaskRead> {
  const response = await client.post<ApiResponse<TaskRead>>(`/tasks/${taskId}/complete`);
  return response.data.data;
}
