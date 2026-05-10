import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getMainProject, listMainProjects } from '@/api/mainProjects';
import { listSubProjects } from '@/api/subProjects';
import { useMainProjectStore } from '@/stores/useMainProjectStore';

vi.mock('@/api/mainProjects', () => ({
  getMainProject: vi.fn(),
  listMainProjects: vi.fn(),
}));

vi.mock('@/api/subProjects', () => ({
  listSubProjects: vi.fn(),
}));

describe('useMainProjectStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listMainProjects).mockResolvedValue({
      items: [sampleMainProject],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(getMainProject).mockResolvedValue(sampleMainProject);
    vi.mocked(listSubProjects).mockResolvedValue({
      items: [sampleSubProject],
      page: 1,
      page_size: 100,
      total: 1,
    });
  });

  it('loads main project list and detail subprojects', async () => {
    const store = useMainProjectStore();

    await store.fetchMainProjects({ page: 1, pageSize: 20 });
    await store.fetchMainProjectDetail('main-1');

    expect(listMainProjects).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(getMainProject).toHaveBeenCalledWith('main-1');
    expect(listSubProjects).toHaveBeenCalledWith({ page: 1, pageSize: 100 });
    expect(store.projects[0].name).toBe('智慧档案平台');
    expect(store.currentProject?.id).toBe('main-1');
    expect(store.currentSubProjects[0].main_project_id).toBe('main-1');
  });
});

const sampleMainProject = {
  created_at: '2026-05-10T00:00:00Z',
  creator_id: 'user-1',
  dept_id: 'dept-a',
  expected_finish_date: '2026-12-31',
  id: 'main-1',
  name: '智慧档案平台',
  project_no: 'Z-2026-0001',
  remark: null,
  spent_amount: '0.00',
  status: 'in_progress',
  total_budget: '500000.00',
  updated_at: '2026-05-10T00:00:00Z',
} as const;

const sampleSubProject = {
  actual_end_date: null,
  budget: '100000.00',
  created_at: '2026-05-10T00:00:00Z',
  creator_id: 'leader-1',
  dept_id: 'dept-a',
  id: 'sub-1',
  main_project_id: 'main-1',
  manager_id: 'leader-1',
  name: '采购实施',
  plan_end_date: '2026-10-31',
  project_no: 'Z-2026-0001-ZX-001',
  remark: null,
  spent_amount: '0.00',
  status: 'in_progress',
  updated_at: '2026-05-10T00:00:00Z',
} as const;
