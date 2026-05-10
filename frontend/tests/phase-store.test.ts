import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getPhase, listPhases, promotePhase } from '@/api/phases';
import { usePhaseStore } from '@/stores/usePhaseStore';
import type { PhaseRead } from '@/types/phases';

vi.mock('@/api/phases', () => ({
  getPhase: vi.fn(),
  listPhases: vi.fn(),
  promotePhase: vi.fn(),
}));

describe('phase store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads phases and updates current and activated phases after promotion', async () => {
    vi.mocked(listPhases).mockResolvedValue({ items: [phaseOne, phaseTwo, phaseThree], total: 3 });
    vi.mocked(getPhase).mockResolvedValue(phaseTwoDetail);
    vi.mocked(promotePhase).mockResolvedValue({
      activated_phase: { ...phaseThree, status: 'in_progress' },
      phase: { ...phaseTwo, status: 'completed' },
    });
    const store = usePhaseStore();

    await store.fetchPhases('sub-1');
    await store.fetchPhaseDetail('phase-2');
    await store.promotePhase('phase-2');

    expect(listPhases).toHaveBeenCalledWith({ subProjectId: 'sub-1' });
    expect(store.currentPhase?.id).toBe('phase-2');
    expect(store.phases.map((phase) => phase.status)).toEqual([
      'completed',
      'completed',
      'in_progress',
    ]);
    expect(store.promotingId).toBeNull();
  });
});

const phaseOne: PhaseRead = {
  code: 'init',
  created_at: '2026-05-10T00:00:00Z',
  enter_at: '2026-05-10T00:00:00Z',
  finish_at: '2026-05-11T00:00:00Z',
  id: 'phase-1',
  name: '立项',
  phase_no: 1,
  procurement_type: null,
  status: 'completed',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-11T00:00:00Z',
};

const phaseTwo: PhaseRead = {
  ...phaseOne,
  code: 'contract',
  finish_at: null,
  id: 'phase-2',
  name: '合同签订',
  phase_no: 2,
  status: 'in_progress',
};

const phaseThree: PhaseRead = {
  ...phaseOne,
  code: 'deliver',
  enter_at: null,
  finish_at: null,
  id: 'phase-3',
  name: '供货验收',
  phase_no: 3,
  status: 'waiting',
};

const phaseTwoDetail = {
  ...phaseTwo,
  completion: {
    missing_doc_types: [],
    required_total: 1,
    uploaded_total: 1,
  },
  required_documents: [],
  uploaded_documents: [],
};
