import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { DocumentRead } from '@/types/documents';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface DocumentTypeSuggestion {
  confidence: number;
  doc_type: string;
  reason: string;
  source: string;
}

export interface DocumentClassificationRead {
  current_doc_type: string | null;
  document_id: string | null;
  file_name: string;
  phase_id: string;
  sub_project_id: string;
  suggestions: DocumentTypeSuggestion[];
}

export interface DocumentClassificationSuggestPayload {
  currentDocType?: string | null;
  documentId?: string | null;
  fileName: string;
  phaseId: string;
  subProjectId: string;
  summary?: string | null;
}

export async function suggestDocumentType(
  payload: DocumentClassificationSuggestPayload,
  client: AxiosInstance = apiClient,
): Promise<DocumentClassificationRead> {
  const response = await client.post<ApiResponse<DocumentClassificationRead>>(
    '/document-classification/suggestions',
    {
      current_doc_type: payload.currentDocType,
      document_id: payload.documentId,
      file_name: payload.fileName,
      phase_id: payload.phaseId,
      sub_project_id: payload.subProjectId,
      summary: payload.summary,
    },
  );
  return response.data.data;
}

export async function confirmDocumentType(
  documentId: string,
  docType: string,
  client: AxiosInstance = apiClient,
): Promise<DocumentRead> {
  const response = await client.post<ApiResponse<DocumentRead>>(
    `/document-classification/documents/${documentId}/confirm`,
    {
      doc_type: docType,
    },
  );
  return response.data.data;
}
