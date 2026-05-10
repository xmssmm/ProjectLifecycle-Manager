import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type { AuditLogListQuery, AuditLogListRead } from '@/types/auditLogs';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listAuditLogs(
  query: AuditLogListQuery = {},
  client: AxiosInstance = apiClient,
): Promise<AuditLogListRead> {
  const response = await client.get<ApiResponse<AuditLogListRead>>('/audit-logs', {
    params: {
      action: query.action,
      actor_id: query.actorId,
      created_from: query.createdFrom,
      created_to: query.createdTo,
      page: query.page,
      page_size: query.pageSize,
      target_id: query.targetId,
      target_type: query.targetType,
    },
  });
  return response.data.data;
}
