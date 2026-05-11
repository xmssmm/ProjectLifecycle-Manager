import { describe, expect, it, vi } from 'vitest';

import {
  createCustomReport,
  deleteCustomReport,
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

describe('custom reports api', () => {
  it('maps custom report endpoints to backend routes', async () => {
    const client = {
      delete: vi.fn(() => Promise.resolve({ data: { data: report } })),
      get: vi.fn((url: string) => {
        if (url === '/custom-reports/datasets') {
          return Promise.resolve({ data: { data: [dataset] } });
        }
        return Promise.resolve({ data: { data: [report] } });
      }),
      post: vi.fn((url: string) => {
        if (url === '/custom-reports/preview') {
          return Promise.resolve({ data: { data: preview } });
        }
        return Promise.resolve({ data: { data: report } });
      }),
    };

    await expect(listCustomReportDatasets(client as never)).resolves.toEqual([dataset]);
    await expect(listCustomReports(client as never)).resolves.toEqual([report]);
    await expect(previewCustomReport(queryConfig, client as never)).resolves.toEqual(preview);
    await expect(createCustomReport(createPayload, client as never)).resolves.toEqual(report);
    await expect(deleteCustomReport('report-1', client as never)).resolves.toEqual(report);

    expect(client.get).toHaveBeenCalledWith('/custom-reports/datasets');
    expect(client.get).toHaveBeenCalledWith('/custom-reports');
    expect(client.post).toHaveBeenCalledWith('/custom-reports/preview', queryConfig);
    expect(client.post).toHaveBeenCalledWith('/custom-reports', createPayload);
    expect(client.delete).toHaveBeenCalledWith('/custom-reports/report-1');
  });
});

const dataset: ReportDatasetRead = {
  default_scope: 'project',
  description: '主项目预算、状态和基础信息。',
  fields: [
    {
      aggregates: ['count'],
      filter_ops: ['eq', 'contains'],
      key: 'project_no',
      label: '项目编号',
      type: 'string',
    },
  ],
  key: 'project_overview',
  label: '项目概览',
};

const queryConfig: ReportQueryConfig = {
  dataset: 'project_overview',
  dimensions: ['project_no'],
  filters: [],
  limit: 100,
  metrics: [],
  sort: [],
};

const preview: CustomReportPreviewRead = {
  columns: dataset.fields,
  limit: 100,
  row_count: 1,
  rows: [{ project_no: 'Z-2026-0001' }],
};

const createPayload: CustomReportDefinitionCreatePayload = {
  chart_type: 'table',
  description: null,
  name: '项目概览',
  query_config: queryConfig,
  share_scope: 'private',
};

const report: CustomReportDefinitionRead = {
  chart_type: 'table',
  dataset: 'project_overview',
  description: null,
  id: 'report-1',
  is_active: true,
  name: '项目概览',
  owner_dept_id: null,
  owner_id: 'admin-1',
  query_config: queryConfig,
  share_scope: 'private',
};
