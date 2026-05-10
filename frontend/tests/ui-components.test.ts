import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { describe, expect, it } from 'vitest';

import ConfirmDialog from '../src/components/common/ConfirmDialog.vue';
import DataTable from '../src/components/common/DataTable.vue';
import PermissionGate from '../src/components/permission/PermissionGate.vue';
import SearchBar from '../src/components/common/SearchBar.vue';
import StatusTag from '../src/components/common/StatusTag.vue';
import { useAuthStore } from '../src/stores/useAuthStore';

const elementStubs = {
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: {
    props: ['modelValue'],
    template: '<section v-if="modelValue"><slot /><slot name="footer" /></section>',
  },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElOption: { template: '<option><slot /></option>' },
  ElPagination: {
    template:
      '<nav><button class="page" @click="$emit(\'current-change\', 2)">2</button><button class="size" @click="$emit(\'size-change\', 50)">50</button></nav>',
  },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElTable: {
    props: ['data'],
    template:
      '<table><tbody><tr v-for="row in data" :key="row.id"><td>{{ row.name }}</td><td>{{ row.status }}</td></tr></tbody><slot /></table>',
  },
  ElTableColumn: { template: '<col />' },
  ElTag: { props: ['type'], template: '<span :data-type="type"><slot /></span>' },
};

describe('common UI components', () => {
  it('DataTable renders rows and emits pagination changes', async () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [
          { key: 'name', label: '名称' },
          { key: 'status', label: '状态' },
        ],
        page: 1,
        pageSize: 20,
        rows: [{ id: '1', name: '主项目 A', status: 'draft' }],
        total: 60,
      },
      global: { directives: { loading: {} }, stubs: elementStubs },
    });

    expect(wrapper.text()).toContain('主项目 A');

    await wrapper.find('.page').trigger('click');
    await wrapper.find('.size').trigger('click');

    expect(wrapper.emitted('update:page')?.[0]).toEqual([2]);
    expect(wrapper.emitted('update:pageSize')?.[0]).toEqual([50]);
  });

  it('DataTable renders a mobile card list with column labels', () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [
          { key: 'project_no', label: '项目编号' },
          { key: 'name', label: '项目名称' },
          { key: 'status', label: '状态' },
        ],
        page: 1,
        pageSize: 20,
        rows: [{ id: '1', name: '主项目 A', project_no: 'Z-2026-0001', status: 'in_progress' }],
        total: 1,
      },
      global: { directives: { loading: {} }, stubs: elementStubs },
    });

    expect(wrapper.find('[data-test="data-table-mobile-list"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="data-table-mobile-card"]').text()).toContain('项目编号');
    expect(wrapper.find('[data-test="data-table-mobile-card"]').text()).toContain('Z-2026-0001');
  });

  it('SearchBar updates fields, emits search, and resets values', async () => {
    const wrapper = mount(SearchBar, {
      props: {
        fields: [
          { key: 'keyword', label: '关键字', type: 'text' },
          {
            key: 'status',
            label: '状态',
            options: [{ label: '草稿', value: 'draft' }],
            type: 'select',
          },
        ],
        modelValue: { keyword: '', status: '' },
      },
      global: { stubs: elementStubs },
    });

    await wrapper.find('input').setValue('项目');
    await wrapper.find('select').setValue('draft');
    await wrapper.findAll('button')[0].trigger('click');
    await wrapper.findAll('button')[1].trigger('click');

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([{ keyword: '项目', status: '' }]);
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([
      { keyword: '项目', status: 'draft' },
    ]);
    expect(wrapper.emitted('update:modelValue')?.[2]).toEqual([{ keyword: '', status: '' }]);
    expect(wrapper.emitted('search')?.[0]).toEqual([{ keyword: '项目', status: 'draft' }]);
    expect(wrapper.emitted('reset')).toBeTruthy();
  });

  it('StatusTag maps known and unknown statuses to labels', () => {
    const approved = mount(StatusTag, {
      props: { status: 'approved' },
      global: { stubs: elementStubs },
    });
    const unknown = mount(StatusTag, {
      props: { status: 'custom_status' },
      global: { stubs: elementStubs },
    });

    expect(approved.text()).toBe('已通过');
    expect(approved.find('[data-type="success"]').exists()).toBe(true);
    expect(unknown.text()).toBe('custom_status');
  });

  it('PermissionGate renders allowed content and fallback content', () => {
    setActivePinia(createPinia());
    const authStore = useAuthStore();
    authStore.setUser({
      deptId: null,
      email: null,
      id: 'finance-1',
      role: 'finance_manager',
      status: 'active',
      username: 'finance',
    });

    const allowed = mount(PermissionGate, {
      props: { permission: 'payment.create' },
      slots: { default: 'allowed', fallback: 'fallback' },
    });
    const denied = mount(PermissionGate, {
      props: { permission: 'user.manage' },
      slots: { default: 'allowed', fallback: 'fallback' },
    });

    expect(allowed.text()).toBe('allowed');
    expect(denied.text()).toBe('fallback');
  });

  it('ConfirmDialog emits confirm and closes itself', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: {
        message: '确认提交审核？',
        modelValue: true,
        title: '提交确认',
      },
      global: { stubs: elementStubs },
    });

    await wrapper.findAll('button')[1].trigger('click');

    expect(wrapper.emitted('confirm')).toBeTruthy();
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false]);
  });
});
