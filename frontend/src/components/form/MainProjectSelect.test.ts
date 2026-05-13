import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MainProjectSelect from '@/components/form/MainProjectSelect.vue';
import { useMainProjectStore } from '@/stores/useMainProjectStore';

const ElSelectStub = {
  name: 'ElSelectStub',
  props: {
    modelValue: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  template: '<div data-test="main-project-select-stub"><slot /></div>',
};

const ElOptionStub = {
  name: 'ElOptionStub',
  props: {
    label: {
      type: String,
      required: true,
    },
    value: {
      type: String,
      required: true,
    },
  },
  template: '<span>{{ label }}</span>',
};

describe('MainProjectSelect', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('only offers approved main projects by default', async () => {
    const store = useMainProjectStore();
    store.projects = [
      {
        created_at: '',
        creator_id: 'creator-1',
        creator_name: 'Owner',
        dept_id: 'dept-1',
        dept_name: 'Administration',
        expected_finish_date: '2026-05-31',
        id: 'main-1',
        name: 'Office Upgrade',
        project_no: 'MP001',
        remark: null,
        remaining_amount: '500000.00',
        spent_amount: '0.00',
        status: 'not_started',
        total_budget: '500000.00',
        updated_at: '',
      },
      {
        created_at: '',
        creator_id: 'creator-2',
        dept_id: 'dept-1',
        expected_finish_date: '2026-05-31',
        id: 'main-2',
        name: 'Pending Review Project',
        project_no: 'MP002',
        remark: null,
        spent_amount: '0.00',
        status: 'pending_review',
        total_budget: '100.00',
        updated_at: '',
      },
    ];
    const fetchMainProjects = vi.spyOn(store, 'fetchMainProjects').mockResolvedValue(undefined);

    const wrapper = mount(MainProjectSelect, {
      props: { modelValue: '' },
      global: {
        stubs: {
          ElOption: ElOptionStub,
          ElSelect: ElSelectStub,
        },
      },
    });

    await nextTick();

    expect(fetchMainProjects).toHaveBeenCalledWith({ page: 1, pageSize: 100 });
    expect(wrapper.text()).toContain('Office Upgrade');
    expect(wrapper.text()).not.toContain('Pending Review Project');
  });
});
