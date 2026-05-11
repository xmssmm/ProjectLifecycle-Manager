import type { ProjectStatus } from '@/types/projects';

export interface ProjectImportRowErrorRead {
  field: string;
  message: string;
  row_number: number;
  value: string | null;
}

export interface ProjectImportCreatedProjectRead {
  dept_id: string;
  id: string;
  name: string;
  project_no: string;
  status: ProjectStatus;
}

export interface ProjectImportResultRead {
  batch_no: string;
  created_projects: ProjectImportCreatedProjectRead[];
  duration_ms: number;
  errors: ProjectImportRowErrorRead[];
  failure_count: number;
  success_count: number;
  total_rows: number;
}
