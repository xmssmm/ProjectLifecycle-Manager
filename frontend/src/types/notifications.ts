export interface NotificationRead {
  created_at: string;
  dedup_key: string;
  id: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  receiver_id: string;
  scenario: string;
  source_id: string;
  updated_at: string;
}

export interface NotificationListRead {
  items: NotificationRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface NotificationListQuery {
  page?: number;
  pageSize?: number;
  unread?: boolean;
}

export interface NotificationUnreadCountRead {
  count: number;
}

export interface NotificationReadAllResult {
  read_count: number;
}
