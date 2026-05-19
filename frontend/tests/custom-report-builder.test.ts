import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createCustomReport,
  deleteCustomReport,
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

describe('CustomReportBuilder', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    const authStore = useAuthStore();
    authStore.setUser({
      deptId: 'dept-1',
      email: 'admin@example.local',
      id: 'admin-1',
      role: 'dept_manager',
      status: 'active',
      username: 'admin',
    });
    vi.clearAllMocks();
    vi.mocked(listCustomReportDatasets).mockResolvedValue([dataset]);
    vi.mocked(listCustomReports).mockResolvedValue([ownedReport, sharedReport]);
    vi.mocked(previewCustomReport).mockResolvedValue(preview);
    vi.mocked(createCustomReport).mockResolvedValue(ownedReport);
    vi.mocked(deleteCustomReport).mockResolvedValue(ownedReport);
  });

  it('loads project datasets and runs a direct project query', async () => {
    const wrapper = mount(CustomReportBuilder, { global: { stubs } });
    await flushPromises();

    expect(listCustomReportDatasets).toHaveBeenCalled();
    expect(wrapper.text()).toContain('项目查询');
    expect(wrapper.text()).not.toContain('设计器');
    expect(wrapper.text()).not.toContain('已保存报表');

    await wrapper.find('[data-test="run-project-query"]').trigger('click');
    await flushPromises();

    expect(previewCustomReport).toHaveBeenCalledWith({
      dataset: 'project_overview',
      dimensions: ['project_no'],
      filters: [],
      limit: 100,
      metrics: [],
      sort: [],
    });
    expect(wrapper.text()).toContain('Z-2026-0001');
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
    {
      aggregates: ['sum', 'avg'],
      filter_ops: ['eq', 'gte', 'lte'],
      key: 'total_budget',
      label: '总预算',
      type: 'number',
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

const ownedReport: CustomReportDefinitionRead = {
  chart_type: 'table',
  dataset: 'project_overview',
  description: null,
  id: 'report-1',
  is_active: true,
  name: '项目概览',
  owner_dept_id: 'dept-1',
  owner_id: 'admin-1',
  query_config: queryConfig,
  share_scope: 'private',
};

const sharedReport: CustomReportDefinitionRead = {
  ...ownedReport,
  id: 'report-2',
  name: '共享报表',
  owner_id: 'other-user',
  share_scope: 'department',
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
  ElCheckboxGroup: {
    props: ['modelValue'],
    template: '<div><slot /></div>',
  },
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
  ElTable: { props: ['data'], template: '<table><slot /></table>' },
  ElTableColumn: { props: ['prop', 'label'], template: '<td>{{ label }}</td>' },
  ElTag: { template: '<span><slot /></span>' },
  ReportChartPreview: {
    props: ['rows'],
    template:
      '<div><span v-for="row in rows" :key="row.project_no">{{ row.project_no }}</span></div>',
  },
};
