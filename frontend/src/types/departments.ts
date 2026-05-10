export interface DepartmentRead {
  code: string;
  created_at: string;
  id: string;
  name: string;
  updated_at: string;
}

export interface DepartmentCreatePayload {
  code: string;
  name: string;
}

export interface DepartmentUpdatePayload {
  code?: string;
  name?: string;
}
