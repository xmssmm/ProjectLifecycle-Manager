export interface WorkflowRequiredDocument {
  doc_type: string;
  procurement_type?: 'bidding' | 'inquiry' | 'single_source' | null;
  qty_rule: string;
  requirement: 'conditional' | 'optional' | 'required';
}

export interface WorkflowPhaseDefinition {
  allow_parallel: boolean;
  entry_rules: Record<string, unknown>;
  key: string;
  name: string;
  order: number;
  required_documents: WorkflowRequiredDocument[];
}

export interface ProjectTypeRead {
  code: string;
  created_at: string;
  description: string | null;
  id: string;
  is_active: boolean;
  is_builtin: boolean;
  name: string;
  updated_at: string;
}

export interface ProjectTypeCreatePayload {
  code: string;
  description?: string | null;
  name: string;
}

export interface WorkflowTemplateVersionRead {
  created_at: string;
  id: string;
  phase_definitions: WorkflowPhaseDefinition[];
  published_at: string | null;
  status: 'archived' | 'draft' | 'published';
  template_id: string;
  updated_at: string;
  version_no: number;
}

export interface WorkflowTemplateRead {
  created_at: string;
  created_by_id: string | null;
  description: string | null;
  id: string;
  name: string;
  project_type_id: string;
  status: 'archived' | 'draft' | 'published';
  updated_at: string;
  versions: WorkflowTemplateVersionRead[];
}

export interface WorkflowTemplateCreatePayload {
  description?: string | null;
  name: string;
  projectTypeId: string;
}
