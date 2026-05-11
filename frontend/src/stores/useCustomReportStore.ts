import { defineStore } from 'pinia';

import {
  createCustomReport as createCustomReportRequest,
  deleteCustomReport as deleteCustomReportRequest,
  listCustomReportDatasets,
  listCustomReports,
  previewCustomReport,
} from '@/api/customReports';
import type {
  CustomReportDefinitionCreatePayload,
  CustomReportDefinitionRead,
  CustomReportPreviewRead,
  ReportDatasetRead,
  ReportQueryConfig,
} from '@/types/customReports';

interface CustomReportState {
  datasets: ReportDatasetRead[];
  loading: boolean;
  preview: CustomReportPreviewRead | null;
  previewing: boolean;
  reports: CustomReportDefinitionRead[];
  submitting: boolean;
}

export const useCustomReportStore = defineStore('customReports', {
  state: (): CustomReportState => ({
    datasets: [],
    loading: false,
    preview: null,
    previewing: false,
    reports: [],
    submitting: false,
  }),
  actions: {
    async fetchMetadata(): Promise<void> {
      this.loading = true;
      try {
        const [datasets, reports] = await Promise.all([
          listCustomReportDatasets(),
          listCustomReports(),
        ]);
        this.datasets = datasets;
        this.reports = reports;
      } finally {
        this.loading = false;
      }
    },
    async previewReport(queryConfig: ReportQueryConfig): Promise<CustomReportPreviewRead> {
      this.previewing = true;
      try {
        const result = await previewCustomReport(queryConfig);
        this.preview = result;
        return result;
      } finally {
        this.previewing = false;
      }
    },
    async createReport(
      payload: CustomReportDefinitionCreatePayload,
    ): Promise<CustomReportDefinitionRead> {
      this.submitting = true;
      try {
        const result = await createCustomReportRequest(payload);
        this.reports = [result, ...this.reports.filter((item) => item.id !== result.id)];
        return result;
      } finally {
        this.submitting = false;
      }
    },
    async deleteReport(reportId: string): Promise<CustomReportDefinitionRead> {
      this.submitting = true;
      try {
        const result = await deleteCustomReportRequest(reportId);
        this.reports = this.reports.filter((item) => item.id !== reportId);
        return result;
      } finally {
        this.submitting = false;
      }
    },
  },
});
