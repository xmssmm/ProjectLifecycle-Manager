import { defineStore } from 'pinia';

import { fetchProjectBenchmark } from '@/api/projectBenchmarks';
import type { ProjectBenchmarkRead } from '@/types/projectBenchmarks';

interface ProjectBenchmarkState {
  benchmark: ProjectBenchmarkRead | null;
  loading: boolean;
}

export const useProjectBenchmarkStore = defineStore('projectBenchmark', {
  state: (): ProjectBenchmarkState => ({
    benchmark: null,
    loading: false,
  }),
  actions: {
    async fetchBenchmark(projectId: string): Promise<ProjectBenchmarkRead> {
      this.loading = true;
      try {
        const result = await fetchProjectBenchmark(projectId);
        this.benchmark = result;
        return result;
      } finally {
        this.loading = false;
      }
    },
  },
});
