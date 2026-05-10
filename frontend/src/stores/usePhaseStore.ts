import { defineStore } from 'pinia';

import { getPhase, listPhases, promotePhase as promotePhaseRequest } from '@/api/phases';
import type {
  PhaseDetailRead,
  PhaseListQuery,
  PhasePromotionRead,
  PhaseRead,
} from '@/types/phases';

interface PhaseState {
  currentPhase: PhaseDetailRead | PhaseRead | null;
  detailLoading: boolean;
  listQuery: PhaseListQuery | null;
  loading: boolean;
  phases: PhaseRead[];
  promotingId: string | null;
  total: number;
}

export const usePhaseStore = defineStore('phases', {
  state: (): PhaseState => ({
    currentPhase: null,
    detailLoading: false,
    listQuery: null,
    loading: false,
    phases: [],
    promotingId: null,
    total: 0,
  }),
  actions: {
    async fetchPhases(subProjectId: string) {
      const query = { subProjectId };
      this.loading = true;
      this.listQuery = query;
      try {
        const result = await listPhases(query);
        this.phases = result.items.sort(comparePhaseNo);
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async fetchPhaseDetail(phaseId: string) {
      this.detailLoading = true;
      try {
        const phase = await getPhase(phaseId);
        this.currentPhase = phase;
        this.upsertPhase(phase);
        return phase;
      } finally {
        this.detailLoading = false;
      }
    },
    async promotePhase(phaseId: string): Promise<PhasePromotionRead> {
      this.promotingId = phaseId;
      try {
        const result = await promotePhaseRequest(phaseId);
        this.currentPhase = result.phase;
        this.upsertPhase(result.phase);
        if (result.activated_phase) {
          this.upsertPhase(result.activated_phase);
        }
        return result;
      } finally {
        this.promotingId = null;
      }
    },
    upsertPhase(phase: PhaseRead) {
      const existingIndex = this.phases.findIndex((item) => item.id === phase.id);
      if (existingIndex >= 0) {
        this.phases.splice(existingIndex, 1, phase);
      } else {
        this.phases.push(phase);
        this.total = Math.max(this.total, this.phases.length);
      }
      this.phases.sort(comparePhaseNo);
    },
  },
});

function comparePhaseNo(left: PhaseRead, right: PhaseRead): number {
  return left.phase_no - right.phase_no;
}
