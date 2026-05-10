import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listAuditLogs } from '@/api/auditLogs';
import type { AuditLogRead } from '@/types/auditLogs';
import AuditLogQuery from '@/views/admin/AuditLogQuery.vue';

vi.mock('@/api/auditLogs', () => ({
  listAuditLogs: vi.fn(),
}));

describe('AuditLogQuery', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listAuditLogs).mockResolvedValue({
      items: [sampleAuditLog],
      page: 1,
      page_size: 20,
      total: 1,
    });
  });

  it('filters audit logs and opens the before/after detail dialog', async () => {
    const wrapper = mount(AuditLogQuery, { global: { stubs } });
    await flushPromises();

    expect(listAuditLogs).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(wrapper.text()).toContain('user.update');

    await wrapper.find('[data-test="audit-filter-actor"]').setValue('actor-1');
    await wrapper.find('[data-test="audit-filter-action"]').setValue('user.update');
    await wrapper.find('[data-test="audit-filter-target-type"]').setValue('user');
    await wrapper.find('[data-test="audit-filter-target-id"]').setValue('user-1');
    await wrapper.find('[data-test="search-audit-logs"]').trigger('click');
    await flushPromises();

    expect(listAuditLogs).toHaveBeenLastCalledWith({
      action: 'user.update',
      actorId: 'actor-1',
      page: 1,
      pageSize: 20,
      targetId: 'user-1',
      targetType: 'user',
    });

    await wrapper.find('[data-test="open-audit-detail"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('old@example.local');
    expect(wrapper.text()).toContain('new@example.local');
    expect(wrapper.text()).toContain('modified_fields');
  });
});

const sampleAuditLog: AuditLogRead = {
  action: 'user.update',
  actor_id: 'actor-1',
  after_state: { email: 'new@example.local' },
  before_state: { email: 'old@example.local' },
  created_at: '2026-05-10T00:00:00Z',
  extra: { modified_fields: { email: true } },
  id: 'audit-1',
  ip_address: '127.0.0.1',
  request_id: 'req-1',
  target_id: 'user-1',
  target_type: 'user',
  updated_at: '2026-05-10T00:00:00Z',
  user_agent: 'pytest',
};

const stubs = {
  ElButton: {
    emits: ['click'],
    props: ['loading', 'type'],
    template:
      '<button type="button" :disabled="loading" @click="$emit(\'click\')"><slot /></button>',
  },
  ElDialog: {
    props: ['modelValue', 'title'],
    template: '<section v-if="modelValue">{{ title }}<slot /></section>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElPagination: { template: '<nav />' },
};
