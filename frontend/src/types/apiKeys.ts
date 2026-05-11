export type ApiKeyPermission = 'projects:read' | 'payments:read' | 'documents:read';

export interface ApiKeyRead {
  created_at: string;
  created_by_id: string;
  expires_at: string | null;
  id: string;
  key_prefix: string;
  last_used_at: string | null;
  name: string;
  permissions: ApiKeyPermission[];
  revoked_at: string | null;
  updated_at: string;
}

export interface ApiKeyCreatePayload {
  expiresAt?: string | null;
  name: string;
  permissions: ApiKeyPermission[];
}

export interface ApiKeyCreateRead {
  api_key: ApiKeyRead;
  token: string;
}

export interface ApiKeyListQuery {
  page: number;
  pageSize: number;
}

export interface ApiKeyListRead {
  items: ApiKeyRead[];
  page: number;
  page_size: number;
  total: number;
}

export const API_KEY_PERMISSION_OPTIONS: Array<{ label: string; value: ApiKeyPermission }> = [
  { label: '项目只读', value: 'projects:read' },
  { label: '付款只读', value: 'payments:read' },
  { label: '文档只读', value: 'documents:read' },
];
