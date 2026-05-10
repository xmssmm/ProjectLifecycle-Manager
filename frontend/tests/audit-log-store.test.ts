import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listAuditLogs } from '@/api/auditLogs';
import { useAuditLogStore } from '@/stores/useAuditLogStore';
import type { AuditLogRead } from '@/types/auditLogs';

vi.mock('@/api/auditLogs', () => ({
  listAuditLogs: vi.fn(),
}));

describe('audit log store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads audit logs with filters and stores pagination state', async () => {
    vi.mocked(listAuditLogs).mockResolvedValue({
      items: [sampleAuditLog],
      page: 2,
      page_size: 25,
      total: 51,
    });
    const store = useAuditLogStore();

    await store.fetchAuditLogs({
      action: 'user.update',
      actorId: 'actor-1',
      page: 2,
      pageSize: 25,
      targetType: 'user',
    });

    expect(listAuditLogs).toHaveBeenCalledWith({
      action: 'user.update',
      actorId: 'actor-1',
      page: 2,
      pageSize: 25,
      targetType: 'user',
    });
    expect(store.auditLogs).toEqual([sampleAuditLog]);
    expect(store.page).toBe(2);
    expect(store.pageSize).toBe(25);
    expect(store.total).toBe(51);
  });
});

const sampleAuditLog: AuditLogRead = {
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
