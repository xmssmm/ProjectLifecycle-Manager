import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { ReportDatasetFieldRead, ReportQueryConfig } from '@/types/customReports';

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface AnalyticsQaChartSuggestion {
  type: string;
  x_field: string | null;
  y_field: string | null;
}

export interface AnalyticsQaAnswerRead {
  answer: string;
  chart: AnalyticsQaChartSuggestion;
  columns: ReportDatasetFieldRead[];
  query_config: ReportQueryConfig;
  question: string;
  row_count: number;
  rows: Record<string, unknown>[];
  source: 'ai' | 'rules';
}

export async function askAnalyticsQuestion(
  question: string,
  client: AxiosInstance = apiClient,
): Promise<AnalyticsQaAnswerRead> {
  const response = await client.post<ApiResponse<AnalyticsQaAnswerRead>>('/analytics-qa/ask', {
    question,
  });
  return response.data.data;
}
