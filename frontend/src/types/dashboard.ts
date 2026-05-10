import type { UserRole } from '@/types/users';

export type DashboardRoleScope = UserRole;

export type DashboardValue = number | string;

export interface DashboardChartPoint {
  label: string;
  value: DashboardValue;
}

export type DashboardMetricMap = Record<string, DashboardValue>;

export type DashboardChartMap = Record<string, DashboardChartPoint[]>;

export type DashboardListItem = Record<string, DashboardValue | null>;

export type DashboardListMap = Record<string, DashboardListItem[]>;

export interface DashboardRead {
  cache_ttl_seconds: number;
  charts: DashboardChartMap;
  generated_at: string;
  lists: DashboardListMap;
  metrics: DashboardMetricMap;
  role_scope: DashboardRoleScope;
}
