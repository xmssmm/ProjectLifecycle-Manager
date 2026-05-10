import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createSubProject,
  getSubProject,
  listSubProjects,
  reviewSubProject,
  submitSubProject,
  terminateSubProject,
} from '@/api/subProjects';
import { useSubProjectStore } from '@/stores/useSubProjectStore';

vi.mock('@/api/subProjects', () => ({
  createSubProject: vi.fn(),
  getSubProject: vi.fn(),
  listSubProjects: vi.fn(),
  reviewSubProject: vi.fn(),
  submitSubProject: vi.fn(),
  terminateSubProject: vi.fn(),
}));

describe('useSubProjectStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listSubProjects).mockResolvedValue({
      items: [sampleSubProject],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(getSubProject).mockResolvedValue(sampleSubProject);
    vi.mocked(createSubProject).mockResolvedValue(sampleSubProject);
    vi.mocked(submitSubProject).mockResolvedValue({
      ...sampleSubProject,
      status: 'pending_review',
    });
    vi.mocked(reviewSubProject).mockResolvedValue({
      ...sampleSubProject,
      status: 'in_progress',
    });
    vi.mocked(terminateSubProject).mockResolvedValue({
      ...sampleSubProject,
      status: 'terminated',
    });
  });

  it('loads list and performs sub project workflow actions', async () => {
    const store = useSubProjectStore();

    await store.fetchSubProjects({ page: 1, pageSize: 20 });
    await store.fetchSubProjectDetail('sub-1');
    const created = await store.createSubProject({
      budget: '100000.00',
      dept_id: 'dept-a',
      main_project_id: 'main-1',
      name: '采购实施',
      plan_end_date: '2026-10-31',
      remark: '一期',
    });
    const submitted = await store.submitSubProject('sub-1');
    const reviewed = await store.reviewSubProject('sub-1', {
      confirm_over_budget: false,
      decision: 'approve',
      over_budget_reason: null,
      review_comment: '通过',
      updates: null,
    });
    const terminated = await store.terminateSubProject('sub-1', { reason: '需求取消' });

    expect(listSubProjects).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(getSubProject).toHaveBeenCalledWith('sub-1');
    expect(createSubProject).toHaveBeenCalledOnce();
    expect(submitSubProject).toHaveBeenCalledWith('sub-1');
    expect(reviewSubProject).toHaveBeenCalledWith('sub-1', {
      confirm_over_budget: false,
      decision: 'approve',
      over_budget_reason: null,
      review_comment: '通过',
      updates: null,
    });
    expect(terminateSubProject).toHaveBeenCalledWith('sub-1', { reason: '需求取消' });
    expect(store.subProjects[0].id).toBe('sub-1');
    expect(store.currentSubProject?.id).toBe('sub-1');
    expect(created.id).toBe('sub-1');
    expect(submitted.status).toBe('pending_review');
    expect(reviewed.status).toBe('in_progress');
    expect(terminated.status).toBe('terminated');
  });
});

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
  status: 'pending_review',
  updated_at: '2026-05-10T00:00:00Z',
} as const;
