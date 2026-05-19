import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  RolePermissionMatrixRead,
  RolePermissionRead,
  RolePermissionUpdate,
} from '@/types/rolePermissions';
import type { UserRole } from '@/types/users';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listRolePermissions(
  client: AxiosInstance = apiClient,
): Promise<RolePermissionMatrixRead> {
  const response = await client.get<ApiResponse<RolePermissionMatrixRead>>('/role-permissions');
  return response.data.data;
}

export async function updateRolePermissions(
  role: UserRole,
  payload: RolePermissionUpdate,
  client: AxiosInstance = apiClient,
): Promise<RolePermissionRead> {
  const response = await client.put<ApiResponse<RolePermissionRead>>(
    `/role-permissions/${role}`,
    payload,
  );
  return response.data.data;
}
