export interface AuditLogRead {
  action: string;
  actor_id: string | null;
  after_state: Record<string, unknown>;
  before_state: Record<string, unknown>;
  created_at: string;
  extra: Record<string, unknown>;
  id: string;
  ip_address: string | null;
  request_id: string | null;
  target_id: string;
  target_type: string;
  updated_at: string;
  user_agent: string | null;
}

export interface AuditLogListRead {
  items: AuditLogRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface AuditLogListQuery {
  action?: string;
  actorId?: string;
  createdFrom?: string;
  createdTo?: string;
  page?: number;
  pageSize?: number;
  targetId?: string;
  targetType?: string;
}
