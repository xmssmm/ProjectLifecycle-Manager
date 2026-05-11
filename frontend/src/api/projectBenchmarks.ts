import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { ProjectBenchmarkRead } from '@/types/projectBenchmarks';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function fetchProjectBenchmark(
  projectId: string,
  client: AxiosInstance = apiClient,
): Promise<ProjectBenchmarkRead> {
  const response = await client.get<ApiResponse<ProjectBenchmarkRead>>(
    `/project-benchmarks/${projectId}`,
  );
  return response.data.data;
}
