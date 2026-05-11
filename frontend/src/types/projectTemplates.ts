export type ProjectTemplateScope = 'department' | 'global' | 'private';

export interface ProjectCategoryRead {
  code: string;
  description: string | null;
  id: string;
  is_active: boolean;
  name: string;
}

export interface ProjectTagRead {
  code: string;
  color: string | null;
  id: string;
  is_active: boolean;
  name: string;
}

export interface ProjectTemplateRead {
  category_id: string | null;
  created_at: string;
  default_task_checklist: Record<string, unknown>[];
  description: string | null;
  document_requirements_snapshot: Record<string, unknown>[];
  field_defaults: Record<string, unknown>;
  id: string;
  is_active: boolean;
  name: string;
  owner_dept_id: string | null;
  owner_id: string;
  phase_snapshot: Record<string, unknown>[];
  project_type_id: string | null;
  scope: ProjectTemplateScope;
  source_project_id: string | null;
  source_project_no: string | null;
  tag_ids: string[];
  updated_at: string;
}

export interface ProjectCategoryCreatePayload {
  code: string;
  description?: string | null;
  name: string;
}

export interface ProjectTagCreatePayload {
  code: string;
  color?: string | null;
  name: string;
}

export interface ProjectTemplateCreateFromProjectPayload {
  category_id?: string | null;
  copy_document_requirements: boolean;
  copy_phase_plan: boolean;
  copy_task_checklist: boolean;
  description?: string | null;
  name: string;
  scope: ProjectTemplateScope;
  source_project_id: string;
  tag_ids: string[];
}

export interface ProjectTemplateInstantiatePayload {
  dept_id?: string | null;
  expected_finish_date?: string | null;
  name?: string | null;
  remark?: string | null;
  total_budget?: string | null;
}
