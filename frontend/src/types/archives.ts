import type { MainProjectRead } from '@/types/projects';

export interface ArchiveCandidateRead {
  closed_at: string;
  main_project_id: string;
  name: string;
  project_no: string;
  sub_project_count: number;
}

export interface ArchiveRunResultRead {
  archived_main_project_count: number;
  archived_sub_project_count: number;
  batch_id: string;
  batch_no: string;
  duration_ms: number;
  main_projects_after: number;
  main_projects_before: number;
}

export interface ArchiveBatchRead {
  archived_main_project_count: number;
  archived_sub_project_count: number;
  batch_no: string;
  created_at: string;
  created_by_id: string | null;
  duration_ms: number;
  finished_at: string;
  id: string;
  started_at: string;
  status: string;
  updated_at: string;
}

export interface ArchiveMainProjectRead {
  archived_at: string;
  batch_id: string;
  closed_at: string | null;
  created_at: string;
  id: string;
  name: string;
  original_id: string;
  project_no: string;
  snapshot: Record<string, unknown>;
  status: string;
  updated_at: string;
}

export interface ArchiveSubProjectRead {
  archived_at: string;
  batch_id: string;
  closed_at: string | null;
  created_at: string;
  id: string;
  name: string;
  original_id: string;
  original_main_project_id: string;
  project_no: string;
  snapshot: Record<string, unknown>;
  status: string;
  updated_at: string;
}

export interface ArchiveBatchListQuery {
  page: number;
  pageSize: number;
}

export interface ArchiveBatchListRead {
  items: ArchiveBatchRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface ArchiveBatchDetailRead {
  batch: ArchiveBatchRead;
  main_projects: ArchiveMainProjectRead[];
  sub_projects: ArchiveSubProjectRead[];
}

export type ArchiveRestoreResultRead = MainProjectRead;
