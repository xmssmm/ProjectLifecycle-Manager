export type WebhookEventType =
  | 'project.status_changed'
  | 'payment.created'
  | 'phase.promoted'
  | 'revoke_request.reviewed';

export type WebhookDeliveryStatus =
  | 'pending'
  | 'retry_scheduled'
  | 'delivered'
  | 'dead_letter';

export interface WebhookEndpointRead {
  created_at: string;
  created_by_id: string;
  event_types: WebhookEventType[];
  id: string;
  is_active: boolean;
  name: string;
  secret_set: boolean;
  updated_at: string;
  url: string;
}

export interface WebhookEndpointCreatePayload {
  eventTypes: WebhookEventType[];
  name: string;
  secret: string;
  url: string;
}

export interface WebhookEndpointListQuery {
  page: number;
  pageSize: number;
}

export interface WebhookEndpointListRead {
  items: WebhookEndpointRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface WebhookDeliveryRead {
  attempt_count: number;
  created_at: string;
  delivered_at: string | null;
  endpoint_id: string;
  event_id: string;
  event_type: WebhookEventType;
  id: string;
  last_attempt_at: string | null;
  last_error: string | null;
  max_attempts: number;
  next_retry_at: string | null;
  payload: Record<string, unknown>;
  response_status: number | null;
  source_id: string;
  status: WebhookDeliveryStatus;
  updated_at: string;
}

export interface WebhookDeliveryListQuery {
  page: number;
  pageSize: number;
}

export interface WebhookDeliveryListRead {
  items: WebhookDeliveryRead[];
  page: number;
  page_size: number;
  total: number;
}

export const WEBHOOK_EVENT_OPTIONS: Array<{ label: string; value: WebhookEventType }> = [
  { label: '项目状态变更', value: 'project.status_changed' },
  { label: '付款发生', value: 'payment.created' },
  { label: '环节推进', value: 'phase.promoted' },
  { label: '撤销审核完成', value: 'revoke_request.reviewed' },
];
