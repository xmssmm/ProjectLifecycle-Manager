import { defineStore } from 'pinia';

import {
  createAcceptanceStep as createAcceptanceStepRequest,
  listAcceptanceSteps,
  updateAcceptanceStep as updateAcceptanceStepRequest,
} from '@/api/acceptanceSteps';
import type {
  AcceptanceStepCreatePayload,
  AcceptanceStepListRead,
  AcceptanceStepRead,
  AcceptanceStepUpdatePayload,
} from '@/types/acceptanceSteps';

interface AcceptanceStepState {
  creating: boolean;
  loadingByPhase: Record<string, boolean>;
  stepsByPhase: Record<string, AcceptanceStepRead[]>;
  totalsByPhase: Record<string, number>;
  updatingId: string | null;
}

export const useAcceptanceStepStore = defineStore('acceptanceSteps', {
  state: (): AcceptanceStepState => ({
    creating: false,
    loadingByPhase: {},
    stepsByPhase: {},
    totalsByPhase: {},
    updatingId: null,
  }),
  actions: {
    async fetchSteps(phaseId: string): Promise<AcceptanceStepListRead> {
      this.loadingByPhase[phaseId] = true;
      try {
        const result = await listAcceptanceSteps(phaseId);
        this.stepsByPhase[phaseId] = result.items.sort(compareStepNo);
        this.totalsByPhase[phaseId] = result.total;
        return result;
      } finally {
        this.loadingByPhase[phaseId] = false;
      }
    },
    async createStep(phaseId: string, payload: AcceptanceStepCreatePayload) {
      this.creating = true;
      try {
        const step = await createAcceptanceStepRequest(phaseId, payload);
        this.upsertStep(phaseId, step);
        return step;
      } finally {
        this.creating = false;
      }
    },
    async updateStep(phaseId: string, stepId: string, payload: AcceptanceStepUpdatePayload) {
      this.updatingId = stepId;
      try {
        const step = await updateAcceptanceStepRequest(phaseId, stepId, payload);
        this.upsertStep(phaseId, step);
        return step;
      } finally {
        this.updatingId = null;
      }
    },
    upsertStep(phaseId: string, step: AcceptanceStepRead) {
      const current = [...(this.stepsByPhase[phaseId] ?? [])];
      const existingIndex = current.findIndex((item) => item.id === step.id);
      if (existingIndex >= 0) {
        current.splice(existingIndex, 1, step);
      } else {
        current.push(step);
      }
      current.sort(compareStepNo);
      this.stepsByPhase[phaseId] = current;
      this.totalsByPhase[phaseId] = Math.max(this.totalsByPhase[phaseId] ?? 0, current.length);
    },
  },
});

function compareStepNo(left: AcceptanceStepRead, right: AcceptanceStepRead): number {
  return left.step_no - right.step_no;
}
