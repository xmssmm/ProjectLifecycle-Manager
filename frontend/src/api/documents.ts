import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  DocumentListQuery,
  DocumentListRead,
  DocumentRead,
  DocumentUploadPayload,
  UploadProgressHandler,
} from '@/types/documents';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export async function listDocuments(
  query: DocumentListQuery,
  client: AxiosInstance = apiClient,
): Promise<DocumentListRead> {
  const response = await client.get<ApiResponse<DocumentListRead>>('/documents', {
    params: {
      doc_type: query.docType,
      include_history: query.includeHistory ?? false,
      phase_id: query.phaseId,
      sub_project_id: query.subProjectId,
    },
  });
  return response.data.data;
}

export async function uploadDocument(
  payload: DocumentUploadPayload,
  client: AxiosInstance | undefined = apiClient,
  onProgress?: UploadProgressHandler,
): Promise<DocumentRead> {
  const form = new FormData();
  form.append('file', payload.file);
  form.append('sub_project_id', payload.subProjectId);
  form.append('phase_id', payload.phaseId);
  form.append('doc_type', payload.docType);
  if (payload.acceptanceStepId) {
    form.append('acceptance_step_id', payload.acceptanceStepId);
  }

  const response = await (client ?? apiClient).post<ApiResponse<DocumentRead>>('/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (!onProgress || !event.total) {
        return;
      }
      onProgress(Math.round((event.loaded / event.total) * 100));
    },
  });
  return response.data.data;
}

export async function downloadDocument(
  documentId: string,
  client: AxiosInstance = apiClient,
): Promise<Blob> {
  const response = await client.get<Blob>(`/documents/${documentId}/download`, {
    responseType: 'blob',
  });
  return response.data;
}
