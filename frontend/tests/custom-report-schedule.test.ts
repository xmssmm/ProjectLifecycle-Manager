import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createCustomReport,
  listCustomReportDatasets,
  listCustomReports,
  previewCustomReport,
} from '@/api/customReports';
import { useAuthStore } from '@/stores/useAuthStore';
import type {
  CustomReportDefinitionRead,
  CustomReportPreviewRead,
  ReportDatasetRead,
  ReportQueryConfig,
} from '@/types/customReports';
import CustomReportBuilder from '@/views/reports/CustomReportBuilder.vue';

vi.mock('@/api/customReports', () => ({
  createCustomReport: vi.fn(),
  deleteCustomReport: vi.fn(),
  listCustomReportDatasets: vi.fn(),
  listCustomReports: vi.fn(),
  previewCustomReport: vi.fn(),
}));

describe('CustomReportBuilder schedule', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    useAuthStore().setUser({
      deptId: 'dept-1',
      email: 'manager@example.local',
      id: 'manager-1',
      role: 'dept_manager',
      status: 'active',
      timezone: 'Asia/Hong_Kong',
      username: 'manager',
    });
    vi.clearAllMocks();
    vi.mocked(listCustomReportDatasets).mockResolvedValue([dataset]);
    vi.mocked(listCustomReports).mockResolvedValue([]);
    vi.mocked(previewCustomReport).mockResolvedValue(preview);
    vi.mocked(createCustomReport).mockResolvedValue(report);
  });

  it('saves weekly schedule settings with the report definition', async () => {
    const wrapper = mount(CustomReportBuilder, { global: { stubs } });
    await flushPromises();

    await wrapper.find('[data-test="report-name"]').setValue('项目周报');
    await wrapper.find('[data-test="schedule-frequency"]').setValue('weekly');
    await wrapper.find('[data-test="schedule-time"]').setValue('09:00');
    await wrapper.find('[data-test="schedule-day-of-week"]').setValue('1');
    await wrapper.find('[data-test="save-report"]').trigger('click');
    await flushPromises();

    expect(createCustomReport).toHaveBeenCalledWith(
      expect.objectContaining({
        schedule_day_of_week: 1,
        schedule_frequency: 'weekly',
        schedule_time: '09:00',
        schedule_timezone: 'Asia/Hong_Kong',
      }),
    );
  });
});

const dataset: ReportDatasetRead = {
  default_scope: 'project',
  description: '项目基础信息',
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
  columns: [dataset.fields[0]],
  limit: 100,
  row_count: 1,
  rows: [{ project_no: 'Z-2026-0001' }],
};

const report: CustomReportDefinitionRead = {
  chart_type: 'table',
  dataset: 'project_overview',
  description: null,
  id: 'report-1',
  is_active: true,
  name: '项目周报',
  next_run_at: '2026-06-01T01:00:00Z',
  owner_dept_id: 'dept-1',
  owner_id: 'manager-1',
  query_config: queryConfig,
  schedule_day_of_month: null,
  schedule_day_of_week: 1,
  schedule_frequency: 'weekly',
  schedule_time: '09:00:00',
  schedule_timezone: 'Asia/Hong_Kong',
  share_scope: 'private',
};

const stubs = {
  DataTable: {
    props: ['rows'],
    template:
      '<table><tbody><tr v-for="row in rows" :key="row.id ?? row.key"><td>{{ row.name ?? row.label ?? row.project_no }}</td><td><slot name="actions" :row="row" /></td></tr></tbody></table>',
  },
  ElButton: {
    props: ['disabled'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElCheckbox: {
    props: ['modelValue', 'label'],
    template:
      '<label><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', label)" />{{ label }}<slot /></label>',
  },
  ElCheckboxGroup: { props: ['modelValue'], template: '<div><slot /></div>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElInputNumber: {
    props: ['modelValue'],
    template:
      '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
  },
  ElOption: { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElTag: { template: '<span><slot /></span>' },
  ReportChartPreview: {
    props: ['rows'],
    template: '<div><span v-for="row in rows" :key="row.project_no">{{ row.project_no }}</span></div>',
  },
};
