import { defineStore } from 'pinia';

import {
  createDatabaseExportJob,
  downloadDatabaseExport,
  getDatabaseExportJob,
} from '@/api/exports';
import type { DatabaseExportJobRead } from '@/types/exports';

interface DatabaseExportState {
  downloading: boolean;
  job: DatabaseExportJobRead | null;
  loading: boolean;
  submitting: boolean;
}

export const useDatabaseExportStore = defineStore('database-exports', {
  state: (): DatabaseExportState => ({
    downloading: false,
    job: null,
    loading: false,
    submitting: false,
  }),
  actions: {
    async createJob(): Promise<DatabaseExportJobRead> {
      this.submitting = true;
      try {
        this.job = await createDatabaseExportJob();
        return this.job;
      } finally {
        this.submitting = false;
      }
    },
    async refreshJob(jobId?: string): Promise<DatabaseExportJobRead | null> {
      const resolvedJobId = jobId ?? this.job?.id;
      if (!resolvedJobId) {
        return null;
      }
      this.loading = true;
      try {
        this.job = await getDatabaseExportJob(resolvedJobId);
        return this.job;
      } finally {
        this.loading = false;
      }
    },
    async downloadJob(jobId?: string): Promise<Blob | null> {
      const resolvedJobId = jobId ?? this.job?.id;
      if (!resolvedJobId) {
        return null;
      }
      this.downloading = true;
      try {
        return await downloadDatabaseExport(resolvedJobId);
      } finally {
        this.downloading = false;
      }
    },
  },
});
