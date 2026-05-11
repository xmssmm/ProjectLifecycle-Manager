import { describe, expect, it, vi } from 'vitest';

import {
  createArchiveBatch,
  getArchiveBatch,
  listArchiveBatches,
  listArchiveCandidates,
  restoreArchiveMainProject,
} from '@/api/archives';

describe('archives api', () => {
  it('maps archive endpoints to backend routes', async () => {
    const client = {
      get: vi.fn((url: string) => {
        if (url === '/archives/candidates') {
          return Promise.resolve({ data: { data: [candidate] } });
        }
        if (url === '/archives/batches') {
          return Promise.resolve({ data: { data: batchList } });
        }
        return Promise.resolve({ data: { data: batchDetail } });
      }),
      post: vi.fn((url: string) => {
        if (url.endsWith('/restore')) {
          return Promise.resolve({ data: { data: restoredProject } });
        }
        return Promise.resolve({ data: { data: runResult } });
      }),
    };

    await expect(listArchiveCandidates(client as never)).resolves.toEqual([candidate]);
    await expect(listArchiveBatches({ page: 2, pageSize: 10 }, client as never)).resolves.toEqual(
      batchList,
    );
    await expect(getArchiveBatch('batch-1', client as never)).resolves.toEqual(batchDetail);
    await expect(createArchiveBatch(client as never)).resolves.toEqual(runResult);
    await expect(restoreArchiveMainProject('archive-main-1', client as never)).resolves.toEqual(
      restoredProject,
    );

    expect(client.get).toHaveBeenCalledWith('/archives/candidates');
    expect(client.get).toHaveBeenCalledWith('/archives/batches', {
      params: { page: 2, page_size: 10 },
    });
    expect(client.get).toHaveBeenCalledWith('/archives/batches/batch-1');
    expect(client.post).toHaveBeenCalledWith('/archives/batches');
    expect(client.post).toHaveBeenCalledWith('/archives/main-projects/archive-main-1/restore');
  });
});

const candidate = {
  closed_at: '2024-05-10T09:00:00Z',
  main_project_id: 'main-1',
  name: 'Main',
  project_no: 'Z-2022-0001',
  sub_project_count: 2,
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
  status: 'closed',
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
  status: 'closed',
  updated_at: '2026-05-11T12:00:00Z',
};

const batchList = { items: [batch], page: 2, page_size: 10, total: 1 };
const batchDetail = {
  batch,
  main_projects: [archiveMainProject],
  sub_projects: [archiveSubProject],
};
const restoredProject = {
  closed_at: '2024-05-10T09:00:00Z',
  created_at: '2022-05-10T09:00:00Z',
  creator_id: 'admin-1',
  dept_id: 'dept-1',
  expected_finish_date: '2024-05-10',
  id: 'main-1',
  name: 'Main',
  project_no: 'Z-2022-0001',
  remark: null,
  spent_amount: '10000.00',
  status: 'closed',
  total_budget: '100000.00',
  updated_at: '2024-05-10T09:00:00Z',
};
