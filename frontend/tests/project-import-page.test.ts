import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { downloadProjectImportTemplate, importProjectWorkbook } from '@/api/imports';
import ProjectImport from '@/views/admin/ProjectImport.vue';

vi.mock('@/api/imports', () => ({
  downloadProjectImportTemplate: vi.fn(),
  importProjectWorkbook: vi.fn(),
}));

describe('ProjectImport', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(downloadProjectImportTemplate).mockResolvedValue(new Blob(['template']));
    vi.mocked(importProjectWorkbook).mockResolvedValue(importResult);
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:template'),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('downloads the template, uploads a workbook, and renders row errors', async () => {
    const wrapper = mount(ProjectImport, { global: { stubs } });

    await wrapper.find('[data-test="download-project-import-template"]').trigger('click');
    await flushPromises();

    expect(downloadProjectImportTemplate).toHaveBeenCalled();

    const file = new File(['xlsx'], 'projects.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const input = wrapper.find('[data-test="project-import-file"]').element as HTMLInputElement;
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    await wrapper.find('[data-test="project-import-file"]').trigger('change');
    await wrapper.find('[data-test="submit-project-import"]').trigger('click');
    await flushPromises();

    expect(importProjectWorkbook).toHaveBeenCalledWith(file);
    expect(wrapper.text()).toContain('IMPORT-20260511-ABCDEF12');
    expect(wrapper.text()).toContain('Z-2026-0001');
    expect(wrapper.text()).toContain('项目编号重复');
  });
});

const importResult = {
  batch_no: 'IMPORT-20260511-ABCDEF12',
  created_projects: [
    {
      dept_id: 'dept-1',
      id: 'project-1',
      name: 'Imported',
      project_no: 'Z-2026-1001',
      status: 'not_started' as const,
    },
  ],
  duration_ms: 12,
  errors: [
    {
      field: 'project_no',
      message: '项目编号重复',
      row_number: 3,
      value: 'Z-2026-0001',
    },
  ],
  failure_count: 1,
  success_count: 1,
  total_rows: 2,
};

const stubs = {
  DataTable: {
    props: ['columns', 'rows'],
    template:
      '<table><tbody><tr v-for="row in rows" :key="row.id || row.row_number"><td>{{ row.project_no || row.value }}</td><td>{{ row.message }}</td><td><slot name="status" :row="row" /></td></tr></tbody></table>',
  },
  ElAlert: { props: ['title'], template: '<section>{{ title }}</section>' },
  ElButton: {
    props: ['disabled', 'loading'],
    template: '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElTag: { template: '<span><slot /></span>' },
};
