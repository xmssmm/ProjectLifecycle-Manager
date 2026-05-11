import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createWebhookEndpoint,
  listWebhookDeadLetters,
  listWebhookEndpoints,
  replayWebhookDelivery,
  setWebhookEndpointActive,
} from '@/api/webhooks';
import type { WebhookDeliveryRead, WebhookEndpointRead } from '@/types/webhooks';
import WebhookManagement from '@/views/admin/WebhookManagement.vue';

vi.mock('@/api/webhooks', () => ({
  createWebhookEndpoint: vi.fn(),
  listWebhookDeadLetters: vi.fn(),
  listWebhookEndpoints: vi.fn(),
  replayWebhookDelivery: vi.fn(),
  setWebhookEndpointActive: vi.fn(),
}));

describe('WebhookManagement', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listWebhookEndpoints).mockResolvedValue({
      items: [sampleEndpoint],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(listWebhookDeadLetters).mockResolvedValue({
      items: [sampleDelivery],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(createWebhookEndpoint).mockResolvedValue(sampleEndpoint);
    vi.mocked(setWebhookEndpointActive).mockResolvedValue({
      ...sampleEndpoint,
      is_active: false,
    });
    vi.mocked(replayWebhookDelivery).mockResolvedValue({
      ...sampleDelivery,
      attempt_count: 0,
      status: 'pending',
    });
  });

  it('creates webhook endpoint without displaying the secret', async () => {
    const wrapper = mount(WebhookManagement, { global: { stubs } });
    await flushPromises();

    expect(listWebhookEndpoints).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(wrapper.text()).not.toContain('top-secret');

    await wrapper.find('[data-test="create-webhook"]').trigger('click');
    await wrapper.find('[data-test="webhook-name"]').setValue('ERP');
    await wrapper.find('[data-test="webhook-url"]').setValue('https://erp.example.local/webhook');
    await wrapper.find('[data-test="webhook-secret"]').setValue('top-secret');
    await wrapper.find('[data-test="webhook-event-payment"] input').setValue(true);
    await wrapper.find('[data-test="submit-webhook"]').trigger('click');
    await flushPromises();

    expect(createWebhookEndpoint).toHaveBeenCalledWith({
      eventTypes: ['payment.created'],
      name: 'ERP',
      secret: 'top-secret',
      url: 'https://erp.example.local/webhook',
    });
    expect(wrapper.text()).not.toContain('top-secret');
  });

  it('toggles endpoint and replays dead letter delivery', async () => {
    const wrapper = mount(WebhookManagement, { global: { stubs } });
    await flushPromises();

    await wrapper.find('[data-test="toggle-webhook"]').trigger('click');
    await wrapper.find('[data-test="replay-webhook-delivery"]').trigger('click');
    await flushPromises();

    expect(setWebhookEndpointActive).toHaveBeenCalledWith('endpoint-1', false);
    expect(replayWebhookDelivery).toHaveBeenCalledWith('delivery-1');
  });
});

const sampleEndpoint: WebhookEndpointRead = {
  created_at: '2026-05-11T08:00:00Z',
  created_by_id: 'admin-1',
  event_types: ['payment.created'],
  id: 'endpoint-1',
  is_active: true,
  name: 'ERP',
  secret_set: true,
  updated_at: '2026-05-11T08:00:00Z',
  url: 'https://erp.example.local/webhook',
};

const sampleDelivery: WebhookDeliveryRead = {
  attempt_count: 6,
  created_at: '2026-05-11T08:00:00Z',
  delivered_at: null,
  endpoint_id: 'endpoint-1',
  event_id: 'event-1',
  event_type: 'payment.created',
  id: 'delivery-1',
  last_attempt_at: '2026-05-11T08:00:00Z',
  last_error: 'Webhook returned 500: server error',
  max_attempts: 6,
  next_retry_at: null,
  payload: { amount: '1200.00' },
  response_status: 500,
  source_id: 'payment-1',
  status: 'dead_letter',
  updated_at: '2026-05-11T08:00:00Z',
};

const stubs = {
  DataTable: {
    props: ['columns', 'rows'],
    template:
      '<table><tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.name || row.event_type }}</td><td><slot name="is_active" :row="row" :value="row.is_active" /></td><td><slot name="actions" :row="row" /></td></tr></tbody></table>',
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
  StatusTag: { props: ['status'], template: '<span>{{ status }}</span>' },
};
