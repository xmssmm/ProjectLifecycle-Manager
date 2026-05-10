import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listRevokeRequests, reviewRevokeRequest, submitRevokeRequest } from '@/api/revokeRequests';
import { useRevokeRequestStore } from '@/stores/useRevokeRequestStore';
import type { RevokeRequestRead } from '@/types/revokeRequests';

vi.mock('@/api/revokeRequests', () => ({
  listRevokeRequests: vi.fn(),
  reviewRevokeRequest: vi.fn(),
  submitRevokeRequest: vi.fn(),
}));

describe('revoke request store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads requests and upserts submitted or reviewed requests', async () => {
    vi.mocked(listRevokeRequests).mockResolvedValue({ items: [sampleRequest], total: 1 });
    vi.mocked(submitRevokeRequest).mockResolvedValue(newRequest);
    vi.mocked(reviewRevokeRequest).mockResolvedValue(approvedRequest);
    const store = useRevokeRequestStore();

    await store.fetchRequests({ status: 'pending' });
    await store.submitRequest({ phaseId: 'phase-3', reason: 'wrong phase' });
    await store.reviewRequest('revoke-1', { decision: 'approve', reviewComment: 'ok' });

    expect(listRevokeRequests).toHaveBeenCalledWith({ status: 'pending' });
    expect(submitRevokeRequest).toHaveBeenCalledWith({
      phaseId: 'phase-3',
      reason: 'wrong phase',
    });
    expect(reviewRevokeRequest).toHaveBeenCalledWith('revoke-1', {
      decision: 'approve',
      reviewComment: 'ok',
    });
    expect(store.requests.map((request) => request.id)).toEqual(['revoke-2', 'revoke-1']);
    expect(store.requests[1].status).toBe('approved');
    expect(store.total).toBe(2);
  });
});

const sampleRequest: RevokeRequestRead = {
  created_at: '2026-05-10T00:00:00Z',
  id: 'revoke-1',
  phase_id: 'phase-2',
  reason: 'wrong document',
  requester_id: 'leader-1',
  review_comment: null,
  reviewed_at: null,
  reviewer_id: null,
  status: 'pending',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T00:00:00Z',
};

const newRequest: RevokeRequestRead = {
  ...sampleRequest,
  id: 'revoke-2',
  phase_id: 'phase-3',
  reason: 'wrong phase',
};

const approvedRequest: RevokeRequestRead = {
  ...sampleRequest,
  review_comment: 'ok',
  reviewed_at: '2026-05-11T00:00:00Z',
  reviewer_id: 'admin-1',
  status: 'approved',
};
