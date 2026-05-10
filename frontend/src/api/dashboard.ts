import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { DashboardRead, DashboardRoleScope } from '@/types/dashboard';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function getDashboard(
  roleScope: DashboardRoleScope,
  client: AxiosInstance = apiClient,
): Promise<DashboardRead> {
  const response = await client.get<ApiResponse<DashboardRead>>(`/dashboard/${roleScope}`);
  return response.data.data;
}
