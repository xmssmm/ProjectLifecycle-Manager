import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  CustomReportDefinitionCreatePayload,
  CustomReportDefinitionRead,
  CustomReportPreviewRead,
  ReportDatasetRead,
  ReportQueryConfig,
} from '@/types/customReports';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}
export async function listCustomReportDatasets(
  client: AxiosInstance = apiClient,
): Promise<ReportDatasetRead[]> {
  const response = await client.get<ApiResponse<ReportDatasetRead[]>>('/custom-reports/datasets');
  return response.data.data;
}

export async function previewCustomReport(
  queryConfig: ReportQueryConfig,
  client: AxiosInstance = apiClient,
): Promise<CustomReportPreviewRead> {
  const response = await client.post<ApiResponse<CustomReportPreviewRead>>(
    '/custom-reports/preview',
    queryConfig,
  );
  return response.data.data;
}

export async function createCustomReport(
  payload: CustomReportDefinitionCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<CustomReportDefinitionRead> {
  const response = await client.post<ApiResponse<CustomReportDefinitionRead>>(
    '/custom-reports',
    payload,
  );
  return response.data.data;
}

export async function listCustomReports(
  client: AxiosInstance = apiClient,
): Promise<CustomReportDefinitionRead[]> {
  const response = await client.get<ApiResponse<CustomReportDefinitionRead[]>>('/custom-reports');
  return response.data.data;
}

export async function deleteCustomReport(
  reportId: string,
  client: AxiosInstance = apiClient,
): Promise<CustomReportDefinitionRead> {
  const response = await client.delete<ApiResponse<CustomReportDefinitionRead>>(
    `/custom-reports/${reportId}`,
  );
  return response.data.data;
}
