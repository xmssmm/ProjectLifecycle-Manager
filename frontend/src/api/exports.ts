import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { DatabaseExportJobRead } from '@/types/exports';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function createDatabaseExportJob(
  client: AxiosInstance = apiClient,
): Promise<DatabaseExportJobRead> {
  const response = await client.post<ApiResponse<DatabaseExportJobRead>>('/exports/database');
  return response.data.data;
}

export async function getDatabaseExportJob(
  jobId: string,
  client: AxiosInstance = apiClient,
): Promise<DatabaseExportJobRead> {
  const response = await client.get<ApiResponse<DatabaseExportJobRead>>(
    `/exports/database/${jobId}`,
  );
  return response.data.data;
}

export async function downloadDatabaseExport(
  jobId: string,
  client: AxiosInstance = apiClient,
): Promise<Blob> {
  const response = await client.get<Blob>(`/exports/database/${jobId}/download`, {
    responseType: 'blob',
  });
  return response.data;
}
