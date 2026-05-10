import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listDepartments } from '@/api/departments';
import DepartmentList from '@/views/admin/DepartmentList.vue';

vi.mock('@/api/departments', () => ({
  createDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  listDepartments: vi.fn(),
  updateDepartment: vi.fn(),
}));

describe('DepartmentList', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listDepartments).mockResolvedValue([sampleDepartment]);
  });

  it('loads and renders departments with row actions', async () => {
    const wrapper = mount(DepartmentList, { global: { stubs } });
    await flushPromises();

    expect(listDepartments).toHaveBeenCalled();
    expect(wrapper.text()).toContain('综合部');
    expect(wrapper.find('[data-test="edit-department"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="delete-department"]').exists()).toBe(true);
  });

  it('opens the create department dialog', async () => {
    const wrapper = mount(DepartmentList, { global: { stubs } });
    await flushPromises();

    await wrapper.find('[data-test="create-department"]').trigger('click');

    expect(wrapper.find('[data-test="department-edit-dialog"]').exists()).toBe(true);
  });
});

const sampleDepartment = {
  code: 'general',
  created_at: '2026-05-10T00:00:00Z',
  id: 'dept-1',
  name: '综合部',
  updated_at: '2026-05-10T00:00:00Z',
} as const;

const stubs = {
  ConfirmDialog: {
    props: ['modelValue', 'message', 'title'],
    template: '<section v-if="modelValue">{{ title }}{{ message }}<slot /></section>',
  },
  DataTable: {
    props: ['columns', 'loading', 'page', 'pageSize', 'rows', 'total'],
    template:
      '<section><article v-for="row in rows" :key="row.id"><span>{{ row.code }}</span><span>{{ row.name }}</span><slot name="actions" :row="row" /></article></section>',
  },
  DepartmentEdit: {
    props: ['modelValue'],
    template: '<section v-if="modelValue" data-test="department-edit-dialog"></section>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  SearchBar: { template: '<section><slot /></section>' },
};
