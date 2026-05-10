import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createAcceptanceStep,
  listAcceptanceSteps,
  updateAcceptanceStep,
} from '@/api/acceptanceSteps';
import { useAcceptanceStepStore } from '@/stores/useAcceptanceStepStore';
import type { AcceptanceStepRead } from '@/types/acceptanceSteps';

vi.mock('@/api/acceptanceSteps', () => ({
  createAcceptanceStep: vi.fn(),
  listAcceptanceSteps: vi.fn(),
  updateAcceptanceStep: vi.fn(),
}));

describe('acceptance step store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads steps and upserts created or completed steps by phase', async () => {
    vi.mocked(listAcceptanceSteps).mockResolvedValue({ items: [sampleStep], total: 1 });
    vi.mocked(createAcceptanceStep).mockResolvedValue(createdStep);
    vi.mocked(updateAcceptanceStep).mockResolvedValue(completedStep);
    const store = useAcceptanceStepStore();

    await store.fetchSteps('phase-4');
    await store.createStep('phase-4', {
      description: 'final acceptance',
      planDate: '2026-05-21',
      responsibleId: 'user-3',
      stepName: 'final review',
      stepNo: 2,
    });
    await store.updateStep('phase-4', 'step-1', { status: 'completed' });

    expect(listAcceptanceSteps).toHaveBeenCalledWith('phase-4');
    expect(createAcceptanceStep).toHaveBeenCalledWith('phase-4', {
      description: 'final acceptance',
      planDate: '2026-05-21',
      responsibleId: 'user-3',
      stepName: 'final review',
      stepNo: 2,
    });
    expect(updateAcceptanceStep).toHaveBeenCalledWith('phase-4', 'step-1', {
      status: 'completed',
    });
    expect(store.stepsByPhase['phase-4'].map((step) => step.id)).toEqual(['step-1', 'step-2']);
    expect(store.stepsByPhase['phase-4'][0].status).toBe('completed');
    expect(store.totalsByPhase['phase-4']).toBe(2);
  });
});

const sampleStep: AcceptanceStepRead = {
  completed_at: null,
  created_at: '2026-05-10T00:00:00Z',
  description: 'site acceptance',
  id: 'step-1',
  phase_id: 'phase-4',
  plan_date: '2026-05-20',
  responsible_id: 'user-2',
  status: 'in_progress',
  step_name: 'site acceptance',
  step_no: 1,
  updated_at: '2026-05-10T00:00:00Z',
};

const createdStep: AcceptanceStepRead = {
  ...sampleStep,
  id: 'step-2',
  plan_date: '2026-05-21',
  responsible_id: 'user-3',
  step_name: 'final review',
  step_no: 2,
};

const completedStep: AcceptanceStepRead = {
  ...sampleStep,
  completed_at: '2026-05-22T00:00:00Z',
  status: 'completed',
};
