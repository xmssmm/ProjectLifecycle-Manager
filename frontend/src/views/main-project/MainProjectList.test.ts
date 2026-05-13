import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useMainProjectStore } from '@/stores/useMainProjectStore';
import MainProjectList from '@/views/main-project/MainProjectList.vue';

const DataTableStub = defineComponent({
  name: 'DataTableStub',
  props: {
    columns: {
      type: Array,
      required: true,
    },
    rows: {
      type: Array,
      required: true,
    },
  },
  template: `
    <div>
      <div v-for="(row, index) in rows" :key="index">
        <span v-for="column in columns" :key="column.key">
          <slot :name="column.key" :row="row" :value="row[column.key]">
            {{ row[column.key] }}
          </slot>
        </span>
      </div>
    </div>
  `,
});

describe('MainProjectList', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('shows department name, spent amount, creator name, and created date', async () => {
    const store = useMainProjectStore();
    store.projects = [
      {
        created_at: '2026-05-13T09:00:00+08:00',
        creator_id: 'user-1',
        creator_name: 'Owner',
        dept_id: 'dept-1',
        dept_name: 'Administration',
        expected_finish_date: '2026-06-30',
        id: 'main-1',
        name: 'Office Upgrade',
        project_no: 'MP001',
        remaining_amount: '275000.00',
        remark: null,
        spent_amount: '225000.00',
        status: 'in_progress',
        total_budget: '500000.00',
        updated_at: '',
      },
    ];
    vi.spyOn(store, 'fetchMainProjects').mockResolvedValue(undefined);

    const wrapper = mount(MainProjectList, {
      global: {
        stubs: {
          DataTable: DataTableStub,
          RouterLink: true,
          SearchBar: true,
          StatusTag: true,
          ElButton: { template: '<button type="button"><slot /></button>' },
        },
      },
    });

    await nextTick();

    expect(wrapper.text()).toContain('Administration');
    expect(wrapper.text()).toContain('225,000.00');
    expect(wrapper.text()).toContain('Owner');
    expect(wrapper.text()).toContain('2026-05-13');
  });
});
