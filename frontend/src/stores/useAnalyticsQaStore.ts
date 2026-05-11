import { defineStore } from 'pinia';

import { askAnalyticsQuestion } from '@/api/analyticsQa';
import type { AnalyticsQaAnswerRead } from '@/api/analyticsQa';

interface AnalyticsQaState {
  answer: AnalyticsQaAnswerRead | null;
  loading: boolean;
}

export const useAnalyticsQaStore = defineStore('analyticsQa', {
  state: (): AnalyticsQaState => ({
    answer: null,
    loading: false,
  }),
  actions: {
    async ask(question: string): Promise<AnalyticsQaAnswerRead> {
      this.loading = true;
      try {
        const result = await askAnalyticsQuestion(question);
        this.answer = result;
        return result;
      } finally {
        this.loading = false;
      }
    },
  },
});
