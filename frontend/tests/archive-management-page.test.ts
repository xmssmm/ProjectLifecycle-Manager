import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createArchiveBatch,
  getArchiveBatch,
  listArchiveBatches,
  listArchiveCandidates,
  restoreArchiveMainProject,
} from '@/api/archives';
import ArchiveManagement from '@/views/admin/ArchiveManagement.vue';

vi.mock('@/api/archives', () => ({
  createArchiveBatch: vi.fn(),
  getArchiveBatch: vi.fn(),
  listArchiveBatches: vi.fn(),
  listArchiveCandidates: vi.fn(),
  restoreArchiveMainProject: vi.fn(),
}));

describe('ArchiveManagement', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listArchiveCandidates).mockResolvedValue([candidate]);
    vi.mocked(listArchiveBatches).mockResolvedValue({
      items: [batch],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(createArchiveBatch).mockResolvedValue(runResult);
    vi.mocked(getArchiveBatch).mockResolvedValue(batchDetail);
    vi.mocked(restoreArchiveMainProject).mockResolvedValue(restoredProject);
  });

  it('loads archive data, creates a batch, and restores a main project', async () => {
    const wrapper = mount(ArchiveManagement, { global: { stubs } });
    await flushPromises();

    expect(listArchiveCandidates).toHaveBeenCalled();
    expect(listArchiveBatches).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(wrapper.text()).toContain('Z-2022-0001');

    await wrapper.find('[data-test="create-archive-batch"]').trigger('click');
    await flushPromises();

    expect(createArchiveBatch).toHaveBeenCalled();
    expect(listArchiveCandidates).toHaveBeenCalledTimes(2);

    await wrapper.find('[data-test="view-archive-batch"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-test="restore-archive-main"]').trigger('click');
    await wrapper.find('[data-test="confirm-restore-archive-main"]').trigger('click');
    await flushPromises();

    expect(getArchiveBatch).toHaveBeenCalledWith('batch-1');
    expect(restoreArchiveMainProject).toHaveBeenCalledWith('archive-main-1');
  });
});

const candidate = {
  closed_at: '2024-05-10T09:00:00Z',
  main_project_id: 'main-1',
  name: 'Main',
  project_no: 'Z-2022-0001',
  sub_project_count: 2,
};

const batch = {
  archived_main_project_count: 1,
  archived_sub_project_count: 2,
  batch_no: 'ARCH-20260511-ABCDEF12',
  created_at: '2026-05-11T12:00:00Z',
  created_by_id: 'admin-1',
  duration_ms: 13,
  finished_at: '2026-05-11T12:00:00Z',
  id: 'batch-1',
  started_at: '2026-05-11T12:00:00Z',
  status: 'completed',
  updated_at: '2026-05-11T12:00:00Z',
};

const archiveMainProject = {
  archived_at: '2026-05-11T12:00:00Z',
  batch_id: 'batch-1',
  closed_at: '2024-05-10T09:00:00Z',
  created_at: '2026-05-11T12:00:00Z',
  id: 'archive-main-1',
  name: 'Main',
  original_id: 'main-1',
  project_no: 'Z-2022-0001',
  snapshot: { project_no: 'Z-2022-0001' },
  status: 'closed' as const,
  updated_at: '2026-05-11T12:00:00Z',
};

const archiveSubProject = {
  archived_at: '2026-05-11T12:00:00Z',
  batch_id: 'batch-1',
  closed_at: '2024-05-10T09:00:00Z',
  created_at: '2026-05-11T12:00:00Z',
  id: 'archive-sub-1',
  name: 'Sub',
  original_id: 'sub-1',
  original_main_project_id: 'main-1',
  project_no: 'Z-2022-0001-ZX-001',
  snapshot: { project_no: 'Z-2022-0001-ZX-001' },
  status: 'closed' as const,
  updated_at: '2026-05-11T12:00:00Z',
};

const runResult = {
  archived_main_project_count: 1,
  archived_sub_project_count: 2,
  batch_id: 'batch-1',
  batch_no: 'ARCH-20260511-ABCDEF12',
  duration_ms: 13,
  main_projects_after: 4,
  main_projects_before: 5,
};

const batchDetail = {
  batch,
  main_projects: [archiveMainProject],
  sub_projects: [archiveSubProject],
};

const restoredProject = {
  ...candidate,
  created_at: '2026-05-11T12:00:00Z',
  creator_id: 'admin-1',
  dept_id: 'dept-1',
  expected_finish_date: '2024-05-10',
  id: 'main-1',
  remark: null,
  spent_amount: '10000.00',
  status: 'closed' as const,
  total_budget: '100000.00',
  updated_at: '2026-05-11T12:00:00Z',
};

const stubs = {
  ConfirmDialog: {
    props: ['modelValue', 'message', 'title'],
    template:
      '<section v-if="modelValue">{{ title }}{{ message }}<button data-test="confirm-restore-archive-main" @click="$emit(\'confirm\')">确认</button></section>',
  },
  DataTable: {
    props: ['columns', 'rows'],
    template:
      '<table><tbody><tr v-for="row in rows" :key="row.id || row.main_project_id"><td>{{ row.project_no }}</td><td><slot name="actions" :row="row" /></td></tr></tbody></table>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: {
    props: ['modelValue', 'title'],
    template:
      '<section v-if="modelValue">{{ title }}<slot /><slot name="footer" /></section>',
  },
  ElTabPane: { template: '<section><slot /></section>' },
  ElTabs: { template: '<section><slot /></section>' },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
  StatusTag: { props: ['status'], template: '<span>{{ status }}</span>' },
};
