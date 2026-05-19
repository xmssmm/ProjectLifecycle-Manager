export const DOCUMENT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export type DocumentScanStatus = 'pending' | 'clean' | 'infected' | 'failed';

export interface DocumentRead {
  acceptance_step_id: string | null;
  created_at: string;
  display_name: string;
  doc_no: string;
  doc_type: string;
  file_name: string;
  file_size: number;
  id: string;
  is_deleted: boolean;
  is_latest: boolean;
  phase_id: string;
  scan_status: DocumentScanStatus;
  scan_result: string | null;
  scanned_at: string | null;
  sub_project_id: string;
  updated_at: string;
  uploader_id: string;
  uploader_name?: string | null;
  version: number;
}

export interface DocumentListRead {
  items: DocumentRead[];
  total: number;
}

export interface DocumentListQuery {
  docType?: string;
  includeHistory?: boolean;
  phaseId?: string;
  subProjectId: string;
}

export interface DocumentUploadPayload {
  acceptanceStepId?: string | null;
  displayName?: string | null;
  docType: string;
  file: File;
  phaseId: string;
  subProjectId: string;
}

export type UploadProgressHandler = (percentage: number) => void;
