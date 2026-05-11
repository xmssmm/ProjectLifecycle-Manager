import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createApiKey, listApiKeys, revokeApiKey } from '@/api/apiKeys';
import type { ApiKeyRead } from '@/types/apiKeys';
import ApiKeyManagement from '@/views/admin/ApiKeyManagement.vue';

vi.mock('@/api/apiKeys', () => ({
  createApiKey: vi.fn(),
  listApiKeys: vi.fn(),
  revokeApiKey: vi.fn(),
}));

describe('ApiKeyManagement', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listApiKeys).mockResolvedValue({
      items: [sampleKey],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(createApiKey).mockResolvedValue({
      api_key: sampleKey,
      token: 'mgmt_plain_once',
    });
    vi.mocked(revokeApiKey).mockResolvedValue({
      ...sampleKey,
      revoked_at: '2026-05-11T09:00:00Z',
    });
  });

  it('creates a key and displays the token only after creation', async () => {
    const wrapper = mount(ApiKeyManagement, { global: { stubs } });
    await flushPromises();

    expect(listApiKeys).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(wrapper.text()).not.toContain('mgmt_plain_once');
    expect(wrapper.text()).not.toContain('hashed');

    await wrapper.find('[data-test="create-api-key"]').trigger('click');
    await wrapper.find('[data-test="api-key-name"]').setValue('Reporting');
    await wrapper.find('[data-test="api-key-permission-projects"] input').setValue(true);
    await wrapper.find('[data-test="api-key-expires-at"]').setValue('2026-06-11T08:00');
    await wrapper.find('[data-test="submit-api-key"]').trigger('click');
    await flushPromises();

    expect(createApiKey).toHaveBeenCalledWith({
      expiresAt: new Date('2026-06-11T08:00').toISOString(),
      name: 'Reporting',
      permissions: ['projects:read'],
    });
    expect(wrapper.find('[data-test="created-api-key-token"]').text()).toContain(
      'mgmt_plain_once',
    );
  });

  it('revokes an active key after confirmation', async () => {
    const wrapper = mount(ApiKeyManagement, { global: { stubs } });
    await flushPromises();

    await wrapper.find('[data-test="revoke-api-key"]').trigger('click');
    await wrapper.find('[data-test="confirm-revoke-api-key"]').trigger('click');
    await flushPromises();

    expect(revokeApiKey).toHaveBeenCalledWith('api-key-1');
  });
});

const sampleKey: ApiKeyRead = {
  created_at: '2026-05-11T08:00:00Z',
  created_by_id: 'admin-1',
  expires_at: '2026-06-11T08:00:00Z',
  id: 'api-key-1',
  key_prefix: 'mgmt_live',
  last_used_at: null,
  name: 'Reporting',
  permissions: ['projects:read'],
  revoked_at: null,
  updated_at: '2026-05-11T08:00:00Z',
};

const stubs = {
  ConfirmDialog: {
    props: ['modelValue', 'message', 'title'],
    template:
      '<section v-if="modelValue">{{ title }}{{ message }}<button data-test="confirm-revoke-api-key" @click="$emit(\'confirm\')">确认</button></section>',
  },
  DataTable: {
    props: ['columns', 'rows'],
    template:
      '<table><tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.name }}</td><td>{{ row.key_prefix }}</td><td><slot name="actions" :row="row" /></td></tr></tbody></table>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElCheckbox: {
    props: ['modelValue', 'label'],
    template:
      '<label><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />{{ label }}<slot /></label>',
  },
  ElDialog: {
    props: ['modelValue', 'title'],
    template:
      '<section v-if="modelValue">{{ title }}<slot /><slot name="footer" /></section>',
  },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
  SearchBar: { template: '<section />' },
  StatusTag: { props: ['status'], template: '<span>{{ status }}</span>' },
};
