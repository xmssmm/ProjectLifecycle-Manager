import { defineStore } from 'pinia';

import { downloadProjectImportTemplate, importProjectWorkbook } from '@/api/imports';
import type { ProjectImportResultRead } from '@/types/imports';

interface ProjectImportState {
  downloading: boolean;
  result: ProjectImportResultRead | null;
  submitting: boolean;
}

export const useProjectImportStore = defineStore('project-imports', {
  state: (): ProjectImportState => ({
    downloading: false,
    result: null,
    submitting: false,
  }),
  actions: {
    async downloadTemplate(): Promise<Blob> {
      this.downloading = true;
      try {
        return await downloadProjectImportTemplate();
      } finally {
        this.downloading = false;
      }
    },
    async importWorkbook(file: File): Promise<ProjectImportResultRead> {
      this.submitting = true;
      try {
        const result = await importProjectWorkbook(file);
        this.result = result;
        return result;
      } finally {
        this.submitting = false;
      }
    },
  },
});
