import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  ArchiveBatchDetailRead,
  ArchiveBatchListQuery,
  ArchiveBatchListRead,
  ArchiveCandidateRead,
  ArchiveRestoreResultRead,
  ArchiveRunResultRead,
} from '@/types/archives';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listArchiveCandidates(
  client: AxiosInstance = apiClient,
): Promise<ArchiveCandidateRead[]> {
  const response = await client.get<ApiResponse<ArchiveCandidateRead[]>>('/archives/candidates');
  return response.data.data;
}

export async function listArchiveBatches(
  query: ArchiveBatchListQuery,
  client: AxiosInstance = apiClient,
): Promise<ArchiveBatchListRead> {
  const response = await client.get<ApiResponse<ArchiveBatchListRead>>('/archives/batches', {
    params: {
      page: query.page,
      page_size: query.pageSize,
    },
  });
  return response.data.data;
}

export async function getArchiveBatch(
  batchId: string,
  client: AxiosInstance = apiClient,
): Promise<ArchiveBatchDetailRead> {
  const response = await client.get<ApiResponse<ArchiveBatchDetailRead>>(
    `/archives/batches/${batchId}`,
  );
  return response.data.data;
}

export async function createArchiveBatch(
  client: AxiosInstance = apiClient,
): Promise<ArchiveRunResultRead> {
  const response = await client.post<ApiResponse<ArchiveRunResultRead>>('/archives/batches');
  return response.data.data;
}

export async function restoreArchiveMainProject(
  archiveMainProjectId: string,
  client: AxiosInstance = apiClient,
): Promise<ArchiveRestoreResultRead> {
  const response = await client.post<ApiResponse<ArchiveRestoreResultRead>>(
    `/archives/main-projects/${archiveMainProjectId}/restore`,
  );
  return response.data.data;
}
