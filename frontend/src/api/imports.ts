import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { ProjectImportResultRead } from '@/types/imports';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function downloadProjectImportTemplate(
  client: AxiosInstance = apiClient,
): Promise<Blob> {
  const response = await client.get<Blob>('/imports/projects/template', {
    responseType: 'blob',
  });
  return response.data;
}

export async function importProjectWorkbook(
  file: File,
  client: AxiosInstance = apiClient,
): Promise<ProjectImportResultRead> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await client.post<ApiResponse<ProjectImportResultRead>>(
    '/imports/projects',
    formData,
  );
  return response.data.data;
}
