export interface DocumentSearchResultRead {
  doc_type: string;
  document_id: string;
  file_name: string;
  phase_id: string;
  phase_name: string;
  snippet: string;
  sub_project_id: string;
  sub_project_name: string;
  sub_project_no: string;
}

export interface DocumentSearchResultsRead {
  items: DocumentSearchResultRead[];
  total: number;
}

export interface DocumentSearchQuery {
  q: string;
  scope: 'documents';
}
