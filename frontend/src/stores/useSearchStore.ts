import { defineStore } from 'pinia';

import { searchDocuments } from '@/api/search';
import type { DocumentSearchResultRead, DocumentSearchResultsRead } from '@/types/search';

interface SearchState {
  items: DocumentSearchResultRead[];
  loading: boolean;
  query: string;
  total: number;
}

export const useSearchStore = defineStore('search', {
  state: (): SearchState => ({
    items: [],
    loading: false,
    query: '',
    total: 0,
  }),
  actions: {
    async search(query?: string): Promise<DocumentSearchResultsRead> {
      const cleaned = (query ?? this.query).trim();
      this.query = cleaned;
      if (!cleaned) {
        this.items = [];
        this.total = 0;
        return { items: [], total: 0 };
      }
      this.loading = true;
      try {
        const result = await searchDocuments({ q: cleaned, scope: 'documents' });
        this.items = result.items;
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
  },
});
