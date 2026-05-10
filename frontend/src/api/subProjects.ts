import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { SubProjectListQuery, SubProjectListRead } from '@/types/projects';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export async function listSubProjects(
  query: SubProjectListQuery,
  client: AxiosInstance = apiClient,
): Promise<SubProjectListRead> {
  const response = await client.get<ApiResponse<SubProjectListRead>>('/sub-projects', {
    params: {
      page: query.page,
      page_size: query.pageSize,
    },
  });
  return response.data.data;
}
