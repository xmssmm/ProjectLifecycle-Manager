import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useSubProjectStore } from '@/stores/useSubProjectStore';
import SubProjectList from '@/views/sub-project/SubProjectList.vue';

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

describe('SubProjectList', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('shows main project name, manager name, spent amount, and remaining amount', async () => {
    const store = useSubProjectStore();
    store.subProjects = [
      {
        actual_end_date: null,
        budget: '180000.00',
        created_at: '',
        creator_id: 'creator-1',
        dept_id: 'dept-1',
        dept_name: 'Administration',
        id: 'sub-1',
        main_project_id: 'main-1',
        main_project_name: 'Office Upgrade',
        manager_id: 'user-1',
        manager_name: 'Project Lead',
        name: 'Workstation Procurement',
        plan_end_date: '2026-06-01',
        project_no: 'SP001',
        remaining_amount: '126000.00',
        remark: null,
        spent_amount: '54000.00',
        status: 'in_progress',
        updated_at: '',
      },
    ];
    vi.spyOn(store, 'fetchSubProjects').mockResolvedValue(undefined);

    const wrapper = mount(SubProjectList, {
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

    expect(wrapper.text()).toContain('Office Upgrade');
    expect(wrapper.text()).toContain('Project Lead');
    expect(wrapper.text()).toContain('54,000.00');
    expect(wrapper.text()).toContain('126,000.00');
  });
});
