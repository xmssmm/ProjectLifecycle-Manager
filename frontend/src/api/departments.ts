import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  DepartmentCreatePayload,
  DepartmentRead,
  DepartmentUpdatePayload,
} from '@/types/departments';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export async function listDepartments(
  client: AxiosInstance = apiClient,
): Promise<DepartmentRead[]> {
  const response = await client.get<ApiResponse<DepartmentRead[]>>('/departments');
  return response.data.data;
}

export async function createDepartment(
  payload: DepartmentCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<DepartmentRead> {
  const response = await client.post<ApiResponse<DepartmentRead>>('/departments', payload);
  return response.data.data;
}

export async function updateDepartment(
  departmentId: string,
  payload: DepartmentUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<DepartmentRead> {
  const response = await client.put<ApiResponse<DepartmentRead>>(
    `/departments/${departmentId}`,
    payload,
  );
  return response.data.data;
}

export async function deleteDepartment(
  departmentId: string,
  client: AxiosInstance = apiClient,
): Promise<DepartmentRead> {
  const response = await client.delete<ApiResponse<DepartmentRead>>(`/departments/${departmentId}`);
  return response.data.data;
}
