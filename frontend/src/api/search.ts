import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { DocumentSearchQuery, DocumentSearchResultsRead } from '@/types/search';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function searchDocuments(
  query: DocumentSearchQuery,
  client: AxiosInstance = apiClient,
): Promise<DocumentSearchResultsRead> {
  const response = await client.get<ApiResponse<DocumentSearchResultsRead>>('/search', {
    params: {
      q: query.q,
      scope: query.scope,
    },
  });
  return response.data.data;
}
