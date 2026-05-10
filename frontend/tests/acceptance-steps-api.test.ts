import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  createAcceptanceStep,
  listAcceptanceSteps,
  updateAcceptanceStep,
} from '../src/api/acceptanceSteps';

describe('acceptance steps api', () => {
  it('supports list, create, and update endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: { items: [sampleStep], total: 1 },
    });

    await listAcceptanceSteps('phase-4', client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleStep,
    });
    await createAcceptanceStep(
      'phase-4',
      {
        description: 'final acceptance',
        planDate: '2026-05-20',
        responsibleId: 'user-2',
        stepName: 'site acceptance',
        stepNo: 1,
      },
      client,
    );
    await updateAcceptanceStep('phase-4', 'step-1', { status: 'completed' }, client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      url: '/phases/phase-4/acceptance-steps',
    });
    expect(calls[1]).toMatchObject({
      method: 'post',
      url: '/phases/phase-4/acceptance-steps',
    });
    expect(requestData(calls[1])).toMatchObject({
      description: 'final acceptance',
      plan_date: '2026-05-20',
      responsible_id: 'user-2',
      step_name: 'site acceptance',
      step_no: 1,
    });
    expect(calls[2]).toMatchObject({
      method: 'put',
      url: '/phases/phase-4/acceptance-steps/step-1',
    });
    expect(requestData(calls[2])).toMatchObject({ status: 'completed' });
  });
});

const sampleStep = {
  completed_at: null,
  created_at: '2026-05-10T00:00:00Z',
  description: 'final acceptance',
  id: 'step-1',
  phase_id: 'phase-4',
  plan_date: '2026-05-20',
  responsible_id: 'user-2',
  status: 'in_progress',
  step_name: 'site acceptance',
  step_no: 1,
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
