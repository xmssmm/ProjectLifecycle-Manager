import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createDatabaseExportJob,
  downloadDatabaseExport,
  getDatabaseExportJob,
} from '@/api/exports';
import DatabaseExport from '@/views/admin/DatabaseExport.vue';

vi.mock('@/api/exports', () => ({
  createDatabaseExportJob: vi.fn(),
  downloadDatabaseExport: vi.fn(),
  getDatabaseExportJob: vi.fn(),
}));

describe('DatabaseExport', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(createDatabaseExportJob).mockResolvedValue(completedJob);
    vi.mocked(getDatabaseExportJob).mockResolvedValue(completedJob);
    vi.mocked(downloadDatabaseExport).mockResolvedValue(new Blob(['zip']));
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:database-export'),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('creates a database export job, refreshes status, and downloads the zip package', async () => {
    const wrapper = mount(DatabaseExport, { global: { stubs } });

    await wrapper.find('[data-test="create-database-export"]').trigger('click');
    await flushPromises();

    expect(createDatabaseExportJob).toHaveBeenCalled();
    expect(wrapper.text()).toContain('EXPORT-JOB-1');
    expect(wrapper.text()).toContain('2');

    await wrapper.find('[data-test="refresh-database-export"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-test="download-database-export"]').trigger('click');
    await flushPromises();

    expect(getDatabaseExportJob).toHaveBeenCalledWith('EXPORT-JOB-1');
    expect(downloadDatabaseExport).toHaveBeenCalledWith('EXPORT-JOB-1');
  });
});

const completedJob = {
  created_at: '2026-05-11T12:00:00Z',
  download_url: '/api/v1/exports/database/EXPORT-JOB-1/download',
  error_message: null,
  finished_at: '2026-05-11T12:00:00Z',
  id: 'EXPORT-JOB-1',
  manifest: { total_rows: 2 },
  progress: 100,
  requested_by_id: 'admin-1',
  row_count: 2,
  started_at: '2026-05-11T12:00:00Z',
  status: 'completed' as const,
  table_count: 2,
  updated_at: '2026-05-11T12:00:00Z',
};

const stubs = {
  ElButton: {
    props: ['disabled', 'loading'],
    template: '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElProgress: { props: ['percentage'], template: '<div>{{ percentage }}</div>' },
  ElTag: { template: '<span><slot /></span>' },
};
