import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import { getPhase, listPhases, promotePhase } from '../src/api/phases';

describe('phases api', () => {
  it('supports list, detail, and promote endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { items: [samplePhase], total: 1 },
      message: 'success',
    });

    await listPhases({ subProjectId: 'sub-1' }, client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: samplePhase,
      message: 'success',
    });
    await getPhase('phase-1', client);
    await promotePhase('phase-1', client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { sub_project_id: 'sub-1' },
      url: '/phases',
    });
    expect(calls[1]).toMatchObject({ method: 'get', url: '/phases/phase-1' });
    expect(calls[2]).toMatchObject({ method: 'post', url: '/phases/phase-1/promote' });
  });
});

const samplePhase = {
  code: 'contract',
  created_at: '2026-05-10T00:00:00Z',
  enter_at: '2026-05-10T00:00:00Z',
  finish_at: null,
  id: 'phase-1',
  name: '合同签订',
  phase_no: 2,
  procurement_type: 'inquiry',
  status: 'in_progress',
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
