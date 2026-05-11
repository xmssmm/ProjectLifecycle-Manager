import { defineStore } from 'pinia';

import {
  createArchiveBatch,
  getArchiveBatch,
  listArchiveBatches,
  listArchiveCandidates,
  restoreArchiveMainProject,
} from '@/api/archives';
import type {
  ArchiveBatchDetailRead,
  ArchiveBatchListQuery,
  ArchiveBatchRead,
  ArchiveCandidateRead,
  ArchiveMainProjectRead,
  ArchiveRunResultRead,
} from '@/types/archives';
import type { MainProjectRead } from '@/types/projects';

interface ArchiveState {
  batches: ArchiveBatchRead[];
  candidates: ArchiveCandidateRead[];
  detail: ArchiveBatchDetailRead | null;
  loading: boolean;
  page: number;
  pageSize: number;
  submitting: boolean;
  total: number;
}

export const useArchiveStore = defineStore('archives', {
  state: (): ArchiveState => ({
    batches: [],
    candidates: [],
    detail: null,
    loading: false,
    page: 1,
    pageSize: 20,
    submitting: false,
    total: 0,
  }),
  actions: {
    async fetchCandidates(): Promise<ArchiveCandidateRead[]> {
      this.loading = true;
      try {
        this.candidates = await listArchiveCandidates();
        return this.candidates;
      } finally {
        this.loading = false;
      }
    },
    async fetchBatches(query?: Partial<ArchiveBatchListQuery>) {
      this.page = query?.page ?? this.page;
      this.pageSize = query?.pageSize ?? this.pageSize;
      this.loading = true;
      try {
        const result = await listArchiveBatches({
          page: this.page,
          pageSize: this.pageSize,
        });
        this.batches = result.items;
        this.total = result.total;
        this.page = result.page;
        this.pageSize = result.page_size;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async createBatch(): Promise<ArchiveRunResultRead> {
      this.submitting = true;
      try {
        const result = await createArchiveBatch();
        await Promise.all([
          this.fetchCandidates(),
          this.fetchBatches({ page: 1, pageSize: this.pageSize }),
        ]);
        return result;
      } finally {
        this.submitting = false;
      }
    },
    async fetchBatchDetail(batchId: string): Promise<ArchiveBatchDetailRead> {
      this.detail = await getArchiveBatch(batchId);
      return this.detail;
    },
    async restoreMainProject(archive: ArchiveMainProjectRead): Promise<MainProjectRead> {
      this.submitting = true;
      try {
        const result = await restoreArchiveMainProject(archive.id);
        if (this.detail) {
          this.detail = {
            ...this.detail,
            main_projects: this.detail.main_projects.filter((item) => item.id !== archive.id),
          };
        }
        return result;
      } finally {
        this.submitting = false;
      }
    },
  },
});
