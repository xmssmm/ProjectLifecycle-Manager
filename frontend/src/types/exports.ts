export type DatabaseExportJobStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface DatabaseExportJobRead {
  created_at: string;
  download_url: string | null;
  error_message: string | null;
  finished_at: string | null;
  id: string;
  manifest: Record<string, unknown>;
  progress: number;
  requested_by_id: string;
  row_count: number;
  started_at: string | null;
  status: DatabaseExportJobStatus;
  table_count: number;
  updated_at: string;
}

export const DATABASE_EXPORT_STATUS_LABELS: Record<DatabaseExportJobStatus, string> = {
  completed: '已完成',
  failed: '失败',
  queued: '排队中',
  running: '执行中',
};
