import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createMainProject,
  getMainProject,
  getProjectProgressFunnel,
  listMainProjects,
  reviewMainProject,
  submitMainProject,
  updateMainProject,
} from '@/api/mainProjects';
import { listSubProjects } from '@/api/subProjects';
import { useMainProjectStore } from '@/stores/useMainProjectStore';
import type { ProjectProgressFunnelRead } from '@/types/projects';

vi.mock('@/api/mainProjects', () => ({
  createMainProject: vi.fn(),
  getMainProject: vi.fn(),
  getProjectProgressFunnel: vi.fn(),
  listMainProjects: vi.fn(),
  reviewMainProject: vi.fn(),
  submitMainProject: vi.fn(),
  updateMainProject: vi.fn(),
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
    vi.mocked(getProjectProgressFunnel).mockResolvedValue(sampleFunnel);
    vi.mocked(createMainProject).mockResolvedValue(sampleMainProject);
    vi.mocked(updateMainProject).mockResolvedValue({ ...sampleMainProject, name: '更新后项目' });
    vi.mocked(submitMainProject).mockResolvedValue({
      ...sampleMainProject,
      status: 'pending_review',
    });
    vi.mocked(reviewMainProject).mockResolvedValue({
      ...sampleMainProject,
      status: 'not_started',
    });
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
    expect(getProjectProgressFunnel).toHaveBeenCalledWith('main-1');
    expect(listSubProjects).toHaveBeenCalledWith({ page: 1, pageSize: 100 });
    expect(store.projects[0].name).toBe('智慧档案平台');
    expect(store.currentProject?.id).toBe('main-1');
    expect(store.currentSubProjects[0].main_project_id).toBe('main-1');
    expect(store.progressFunnel?.items[0].name).toBe('采购');
  });

  it('creates, updates, and submits main projects', async () => {
    const store = useMainProjectStore();

    const created = await store.createMainProject({
      dept_id: 'dept-a',
      expected_finish_date: '2026-12-31',
      name: '智慧档案平台',
      remark: '一期',
      total_budget: '500000.00',
    });
    const updated = await store.updateMainProject('main-1', {
      name: '更新后项目',
      remark: null,
    });
    const submitted = await store.submitMainProject('main-1');
    const reviewed = await store.reviewMainProject('main-1', {
      decision: 'approve',
      review_comment: '同意立项',
      updates: { name: '智慧档案平台二期' },
    });

    expect(createMainProject).toHaveBeenCalledWith({
      dept_id: 'dept-a',
      expected_finish_date: '2026-12-31',
      name: '智慧档案平台',
      remark: '一期',
      total_budget: '500000.00',
    });
    expect(updateMainProject).toHaveBeenCalledWith('main-1', {
      name: '更新后项目',
      remark: null,
    });
    expect(submitMainProject).toHaveBeenCalledWith('main-1');
    expect(reviewMainProject).toHaveBeenCalledWith('main-1', {
      decision: 'approve',
      review_comment: '同意立项',
      updates: { name: '智慧档案平台二期' },
    });
    expect(created.id).toBe('main-1');
    expect(updated.name).toBe('更新后项目');
    expect(submitted.status).toBe('pending_review');
    expect(reviewed.status).toBe('not_started');
    expect(store.currentProject?.status).toBe('not_started');
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

const sampleFunnel: ProjectProgressFunnelRead = {
  items: [
    {
      code: 'procurement',
      name: '采购',
      phase_no: 2,
      sub_project_count: 1,
      sub_projects: [
        {
          id: 'sub-1',
          name: '采购实施',
          phase_status: 'in_progress',
          project_no: 'Z-2026-0001-ZX-001',
          status: 'in_progress',
        },
      ],
    },
  ],
  main_project_id: 'main-1',
  total_sub_projects: 1,
};
