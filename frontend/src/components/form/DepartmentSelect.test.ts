import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DepartmentSelect from '@/components/form/DepartmentSelect.vue';
import { useDepartmentStore } from '@/stores/useDepartmentStore';

const ElSelectStub = {
  name: 'ElSelectStub',
  props: {
    modelValue: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  template: `
    <div data-test="department-select-stub" @click="$emit('update:modelValue', 'dept-1')">
      <slot />
    </div>
  `,
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

describe('DepartmentSelect', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('loads departments and emits selected department id', async () => {
    const store = useDepartmentStore();
    store.departments = [
      { code: 'XZ', created_at: '', id: 'dept-1', name: 'Administration', updated_at: '' },
    ];
    const fetchDepartments = vi.spyOn(store, 'fetchDepartments').mockResolvedValue(undefined);

    const wrapper = mount(DepartmentSelect, {
      props: { modelValue: '' },
      global: {
        stubs: {
          ElOption: ElOptionStub,
          ElSelect: ElSelectStub,
        },
      },
    });

    await nextTick();
    await wrapper.get('[data-test="department-select"]').trigger('click');

    expect(fetchDepartments).toHaveBeenCalled();
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['dept-1']);
    expect(wrapper.text()).toContain('Administration');
  });
});
