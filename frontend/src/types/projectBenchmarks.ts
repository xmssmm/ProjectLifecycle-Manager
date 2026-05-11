export type ProjectBenchmarkStatus = 'insufficient_sample' | 'ready';

export interface ProjectBenchmarkMetric {
  average: number | null;
  current_value: number | null;
  key: string;
  label: string;
  p50: number | null;
  p90: number | null;
  sample_count: number;
  unit: string;
}

export interface ProjectBenchmarkScope {
  category_id: string | null;
  dept_id: string;
  project_type_id: string | null;
  tag_ids: string[];
}

export interface ProjectBenchmarkRead {
  metrics: ProjectBenchmarkMetric[];
  project_id: string;
  sample_count: number;
  scope: ProjectBenchmarkScope;
  status: ProjectBenchmarkStatus;
}
