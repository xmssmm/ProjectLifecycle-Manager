import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  listRevokeRequests,
  reviewRevokeRequest,
  submitRevokeRequest,
} from '../src/api/revokeRequests';

describe('revoke requests api', () => {
  it('supports list, submit, and review endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { items: [sampleRequest], total: 1 },
      message: 'success',
    });

    await listRevokeRequests({ status: 'pending' }, client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: sampleRequest,
      message: 'success',
    });
    await submitRevokeRequest(
      {
        keepDocuments: false,
        phaseId: 'phase-2',
        reason: 'wrong document',
      },
      client,
    );
    await reviewRevokeRequest(
      'revoke-1',
      {
        decision: 'approve',
        reviewComment: 'ok',
      },
      client,
    );

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { status: 'pending' },
      url: '/revoke-requests',
    });
    expect(calls[1]).toMatchObject({
      method: 'post',
      url: '/revoke-requests',
    });
    expect(requestData(calls[1])).toMatchObject({
      keep_documents: false,
      phase_id: 'phase-2',
      reason: 'wrong document',
    });
    expect(calls[2]).toMatchObject({
      method: 'post',
      url: '/revoke-requests/revoke-1/review',
    });
    expect(requestData(calls[2])).toMatchObject({
      decision: 'approve',
      review_comment: 'ok',
    });
  });
});

const sampleRequest = {
  created_at: '2026-05-10T00:00:00Z',
  id: 'revoke-1',
  keep_documents: false,
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

function requestData(call: AxiosRequestConfig): unknown {
  return typeof call.data === 'string' ? JSON.parse(call.data) : call.data;
}
