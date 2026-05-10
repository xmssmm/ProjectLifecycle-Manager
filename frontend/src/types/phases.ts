export type PhaseStatus = 'waiting' | 'in_progress' | 'completed' | 'revoked';
export type ProcurementType = 'inquiry' | 'bidding' | 'single_source';
export type PhaseDocRequirement = 'required' | 'conditional' | 'optional';

export interface PhaseRead {
  code: string;
  created_at: string;
  enter_at: string | null;
  finish_at: string | null;
  id: string;
  name: string;
  phase_no: number;
  procurement_type: ProcurementType | null;
  status: PhaseStatus;
  sub_project_id: string;
  updated_at: string;
}

export interface PhaseListRead {
  items: PhaseRead[];
  total: number;
}

export interface PhaseListQuery {
  subProjectId: string;
}

export interface PhaseRequiredDocumentRead {
  doc_type: string;
  procurement_type: ProcurementType | null;
  qty_rule: string;
  requirement: PhaseDocRequirement;
}

export interface PhaseUploadedDocumentRead {
  doc_type: string;
  file_name: string;
  file_size: number;
  id: string;
  uploaded_at: string;
  uploader_id: string;
  version: number;
}

export interface PhaseCompletionRead {
  missing_doc_types: string[];
  required_total: number;
  uploaded_total: number;
}

export interface PhaseDetailRead extends PhaseRead {
  completion: PhaseCompletionRead;
  required_documents: PhaseRequiredDocumentRead[];
  uploaded_documents: PhaseUploadedDocumentRead[];
}

export interface PhasePromotionRead {
  activated_phase: PhaseRead | null;
  phase: PhaseRead;
}

export const PHASE_STATUS_LABELS: Record<PhaseStatus, string> = {
  completed: '已完成',
  in_progress: '进行中',
  revoked: '已撤销',
  waiting: '待开始',
};
