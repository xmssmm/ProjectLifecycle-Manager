import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { listAuditLogs } from '../src/api/auditLogs';
import { createApiClient } from '../src/api/client';

describe('audit logs api', () => {
  it('maps query filters to the audit log endpoint', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { items: [sampleAuditLog], page: 1, page_size: 10, total: 1 },
      message: 'success',
    });

    await listAuditLogs(
      {
        action: 'user.update',
        actorId: 'actor-1',
        createdFrom: '2026-05-01T00:00:00Z',
        createdTo: '2026-06-01T00:00:00Z',
        page: 1,
        pageSize: 10,
        targetId: 'user-1',
        targetType: 'user',
      },
      client,
    );

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: {
        action: 'user.update',
        actor_id: 'actor-1',
        created_from: '2026-05-01T00:00:00Z',
        created_to: '2026-06-01T00:00:00Z',
        page: 1,
        page_size: 10,
        target_id: 'user-1',
        target_type: 'user',
      },
      url: '/audit-logs',
    });
  });
});

const sampleAuditLog = {
  action: 'user.update',
  actor_id: 'actor-1',
  after_state: { email: 'new@example.local' },
  before_state: { email: 'old@example.local' },
  created_at: '2026-05-10T00:00:00Z',
  extra: { modified_fields: { email: true } },
  id: 'audit-1',
  ip_address: '127.0.0.1',
  request_id: 'req-1',
  target_id: 'user-1',
  target_type: 'user',
  updated_at: '2026-05-10T00:00:00Z',
  user_agent: 'pytest',
};

function recordingAdapter(calls: AxiosRequestConfig[], data: unknown): AxiosAdapter {
  return async (config) => {
    calls.push(config);
    return {
      config,
      data,
      headers: {},
      status: 200,
      statusText: 'OK',
    };
  };
}
