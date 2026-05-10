import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createDepartment,
  deleteDepartment,
  listDepartments,
  updateDepartment,
} from '@/api/departments';

import { useDepartmentStore } from '../src/stores/useDepartmentStore';

vi.mock('@/api/departments', () => ({
  createDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  listDepartments: vi.fn(),
  updateDepartment: vi.fn(),
}));

describe('useDepartmentStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listDepartments).mockResolvedValue([sampleDepartment]);
  });

  it('loads departments', async () => {
    const store = useDepartmentStore();

    await store.fetchDepartments();

    expect(listDepartments).toHaveBeenCalled();
    expect(store.departments[0].name).toBe('综合部');
    expect(store.total).toBe(1);
  });

  it('refreshes departments after mutations', async () => {
    vi.mocked(createDepartment).mockResolvedValue(sampleDepartment);
    vi.mocked(updateDepartment).mockResolvedValue(sampleDepartment);
    vi.mocked(deleteDepartment).mockResolvedValue(sampleDepartment);
    const store = useDepartmentStore();
    await store.fetchDepartments();

    await store.createDepartment({ code: 'general', name: '综合部' });
    await store.updateDepartment('dept-1', { name: '综合管理部' });
    await store.deleteDepartment('dept-1');

    expect(listDepartments).toHaveBeenCalledTimes(4);
  });
});

const sampleDepartment = {
  code: 'general',
  created_at: '2026-05-10T00:00:00Z',
  id: 'dept-1',
  name: '综合部',
  updated_at: '2026-05-10T00:00:00Z',
} as const;
