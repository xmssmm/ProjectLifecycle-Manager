<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { DataTable, StatusTag } from '@/components/common';
import { useWebhookStore } from '@/stores/useWebhookStore';
import {
  WEBHOOK_EVENT_OPTIONS,
  type WebhookDeliveryRead,
  type WebhookEndpointRead,
  type WebhookEventType,
} from '@/types/webhooks';

const webhookStore = useWebhookStore();

const createDialogVisible = ref(false);
const validationMessage = ref('');
const form = reactive({
  eventTypes: [] as WebhookEventType[],
  name: '',
  secret: '',
  url: '',
});

const endpointColumns = [
  { key: 'name', label: '名称', minWidth: 140 },
  { key: 'url', label: 'URL', minWidth: 260 },
  { key: 'event_types', label: '事件', minWidth: 220 },
  { key: 'is_active', label: '状态', width: 120 },
  { key: 'actions', label: '操作', width: 120 },
];

const deadLetterColumns = [
  { key: 'event_type', label: '事件', minWidth: 180 },
  { key: 'source_id', label: '来源', minWidth: 140 },
  { key: 'attempt_count', label: '次数', width: 90 },
  { key: 'last_error', label: '错误', minWidth: 260 },
  { key: 'actions', label: '操作', width: 120 },
];

const endpointRows = computed(() => webhookStore.endpoints as unknown as Record<string, unknown>[]);
const deadLetterRows = computed(
  () => webhookStore.deadLetters as unknown as Record<string, unknown>[],
);

onMounted(async () => {
  await Promise.all([
    webhookStore.fetchEndpoints({ page: 1, pageSize: 20 }),
    webhookStore.fetchDeadLetters({ page: 1, pageSize: 20 }),
  ]);
});

function openCreateDialog(): void {
  form.eventTypes = [];
  form.name = '';
  form.secret = '';
  form.url = '';
  validationMessage.value = '';
  createDialogVisible.value = true;
}

function toggleEvent(eventType: WebhookEventType, checked: boolean): void {
  form.eventTypes = checked
    ? [...form.eventTypes, eventType]
    : form.eventTypes.filter((item) => item !== eventType);
}

async function submitCreate(): Promise<void> {
  validationMessage.value = validateForm();
  if (validationMessage.value) {
    return;
  }
  await webhookStore.createEndpoint({
    eventTypes: form.eventTypes,
    name: form.name.trim(),
    secret: form.secret.trim(),
    url: form.url.trim(),
  });
  createDialogVisible.value = false;
  ElMessage.success('Webhook 已创建');
}

async function toggleEndpoint(endpoint: WebhookEndpointRead): Promise<void> {
  await webhookStore.setEndpointActive(endpoint.id, !endpoint.is_active);
  ElMessage.success(endpoint.is_active ? 'Webhook 已停用' : 'Webhook 已启用');
}

async function replayDelivery(delivery: WebhookDeliveryRead): Promise<void> {
  await webhookStore.replayDelivery(delivery.id);
  ElMessage.success('Webhook 死信已重新入队');
}

function validateForm(): string {
  if (!form.name.trim()) {
    return '请输入名称';
  }
  if (!form.url.trim()) {
    return '请输入 URL';
  }
  if (!form.secret.trim()) {
    return '请输入签名密钥';
  }
  if (!form.eventTypes.length) {
    return '请选择至少一个事件';
  }
  return '';
}

function eventLabels(eventTypes: unknown): string {
  if (!Array.isArray(eventTypes)) {
    return '-';
  }
  return eventTypes
    .map((eventType) => {
      const option = WEBHOOK_EVENT_OPTIONS.find((item) => item.value === eventType);
      return option?.label ?? String(eventType);
    })
    .join('、');
}

function endpointStatus(endpoint: WebhookEndpointRead): string {
  return endpoint.is_active ? 'active' : 'disabled';
}
</script>

<template>
  <section class="admin-page webhook-page">
    <div class="admin-page__header">
      <div>
        <h2>Webhook 管理</h2>
        <p>配置外部回调、事件订阅、失败重试和死信重放。</p>
      </div>
      <el-button data-test="create-webhook" type="primary" @click="openCreateDialog">
        创建 Webhook
      </el-button>
    </div>

    <DataTable
      class="admin-page__table"
      :columns="endpointColumns"
      :loading="webhookStore.loading"
      :page="webhookStore.endpointPage"
      :page-size="webhookStore.endpointPageSize"
      :rows="endpointRows"
      :total="webhookStore.endpointTotal"
      @update:page="webhookStore.fetchEndpoints({ page: $event })"
      @update:page-size="webhookStore.fetchEndpoints({ page: 1, pageSize: $event })"
    >
      <template #event_types="{ value }">
        {{ eventLabels(value) }}
      </template>
      <template #is_active="{ row }">
        <StatusTag :status="endpointStatus(row as WebhookEndpointRead)" />
      </template>
      <template #actions="{ row }">
        <el-button
          data-test="toggle-webhook"
          size="small"
          @click="toggleEndpoint(row as WebhookEndpointRead)"
        >
          {{ (row as WebhookEndpointRead).is_active ? '停用' : '启用' }}
        </el-button>
      </template>
    </DataTable>

    <section class="webhook-page__section">
      <h3>死信队列</h3>
      <DataTable
        :columns="deadLetterColumns"
        :loading="webhookStore.loading"
        :page="webhookStore.deadLetterPage"
        :page-size="webhookStore.deadLetterPageSize"
        :rows="deadLetterRows"
        :total="webhookStore.deadLetterTotal"
        @update:page="webhookStore.fetchDeadLetters({ page: $event })"
        @update:page-size="webhookStore.fetchDeadLetters({ page: 1, pageSize: $event })"
      >
        <template #event_type="{ value }">
          {{ eventLabels([value]) }}
        </template>
        <template #actions="{ row }">
          <el-button
            data-test="replay-webhook-delivery"
            size="small"
            type="primary"
            @click="replayDelivery(row as WebhookDeliveryRead)"
          >
            重放
          </el-button>
        </template>
      </DataTable>
    </section>

    <el-dialog v-model="createDialogVisible" title="创建 Webhook" width="560px">
      <el-form label-width="96px">
        <el-form-item label="名称">
          <el-input v-model="form.name" data-test="webhook-name" maxlength="120" />
        </el-form-item>
        <el-form-item label="URL">
          <el-input v-model="form.url" data-test="webhook-url" maxlength="500" />
        </el-form-item>
        <el-form-item label="签名密钥">
          <el-input
            v-model="form.secret"
            data-test="webhook-secret"
            maxlength="255"
            type="password"
          />
        </el-form-item>
        <el-form-item label="事件">
          <div class="webhook-events">
            <el-checkbox
              v-for="eventOption in WEBHOOK_EVENT_OPTIONS"
              :key="eventOption.value"
              :data-test="`webhook-event-${eventOption.value.split('.')[0].split('_')[0]}`"
              :label="eventOption.label"
              :model-value="form.eventTypes.includes(eventOption.value)"
              @update:model-value="toggleEvent(eventOption.value, Boolean($event))"
            />
          </div>
        </el-form-item>
      </el-form>
      <p v-if="validationMessage" class="form-error">{{ validationMessage }}</p>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button
          data-test="submit-webhook"
          :loading="webhookStore.submitting"
          type="primary"
          @click="submitCreate"
        >
          创建
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.webhook-events {
  display: grid;
  gap: 8px;
}

.webhook-page__section {
  margin-top: 24px;
}

.webhook-page__section h3 {
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 12px;
}
</style>
