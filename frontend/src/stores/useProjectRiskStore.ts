import { defineStore } from 'pinia';

import { fetchProjectRisk } from '@/api/projectRisk';
import type { ProjectRiskRead } from '@/types/projectRisk';

interface ProjectRiskState {
  loading: boolean;
  risk: ProjectRiskRead | null;
}

export const useProjectRiskStore = defineStore('projectRisk', {
  state: (): ProjectRiskState => ({
    loading: false,
    risk: null,
  }),
  actions: {
    async fetchRisk(projectId: string): Promise<ProjectRiskRead> {
      this.loading = true;
      try {
        const result = await fetchProjectRisk(projectId);
        this.risk = result;
        return result;
      } finally {
        this.loading = false;
      }
    },
  },
});
