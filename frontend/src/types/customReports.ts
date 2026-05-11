export type DatasetFieldType = 'boolean' | 'date' | 'datetime' | 'enum' | 'number' | 'string' | 'uuid';
export type DatasetAggregate = 'avg' | 'count' | 'count_distinct' | 'max' | 'min' | 'sum';
export type DatasetFilterOperator =
  | 'between'
  | 'contains'
  | 'eq'
  | 'gt'
  | 'gte'
  | 'in'
  | 'is_not_null'
  | 'is_null'
  | 'lt'
  | 'lte'
  | 'ne'
  | 'not_in'
  | 'starts_with';
export type SortDirection = 'asc' | 'desc';
export type CustomReportShareScope = 'department' | 'global' | 'private';
export type CustomReportChartType = 'bar' | 'line' | 'table';
export type CustomReportScheduleFrequency = 'daily' | 'monthly' | 'weekly';

export interface ReportDatasetFieldRead {
  aggregates: DatasetAggregate[];
  filter_ops: DatasetFilterOperator[];
  key: string;
  label: string;
  type: DatasetFieldType;
}
export interface ReportDatasetRead {
  default_scope: string;
  description: string;
  fields: ReportDatasetFieldRead[];
  key: string;
  label: string;
}

export interface ReportMetricConfig {
  aggregate: DatasetAggregate;
  alias?: string | null;
  field: string;
}

export interface ReportFilterConfig {
  field: string;
  op: DatasetFilterOperator;
  value?: unknown;
}

export interface ReportSortConfig {
  direction: SortDirection;
  field: string;
}

export interface ReportQueryConfig {
  dataset: string;
  dimensions: string[];
  filters: ReportFilterConfig[];
  limit: number;
  metrics: ReportMetricConfig[];
  sort: ReportSortConfig[];
}

export interface CustomReportPreviewRead {
  columns: ReportDatasetFieldRead[];
  limit: number;
  row_count: number;
  rows: Record<string, unknown>[];
}

export interface CustomReportDefinitionCreatePayload {
  chart_type: CustomReportChartType;
  description: string | null;
  name: string;
  query_config: ReportQueryConfig;
  schedule_day_of_month?: number | null;
  schedule_day_of_week?: number | null;
  schedule_frequency?: CustomReportScheduleFrequency | null;
  schedule_time?: string | null;
  schedule_timezone?: string | null;
  share_scope: CustomReportShareScope;
}

export interface CustomReportDefinitionRead {
  chart_type: CustomReportChartType;
  dataset: string;
  description: string | null;
  id: string;
  is_active: boolean;
  name: string;
  owner_dept_id: string | null;
  owner_id: string;
  query_config: ReportQueryConfig;
  last_run_at?: string | null;
  next_run_at?: string | null;
  schedule_day_of_month?: number | null;
  schedule_day_of_week?: number | null;
  schedule_frequency?: CustomReportScheduleFrequency | null;
  schedule_time?: string | null;
  schedule_timezone?: string | null;
  share_scope: CustomReportShareScope;
}
