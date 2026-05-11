<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { ConfirmDialog, DataTable, StatusTag } from '@/components/common';
import { useApiKeyStore } from '@/stores/useApiKeyStore';
import {
  API_KEY_PERMISSION_OPTIONS,
  type ApiKeyPermission,
  type ApiKeyRead,
} from '@/types/apiKeys';

const apiKeyStore = useApiKeyStore();

const createDialogVisible = ref(false);
const revokeDialogVisible = ref(false);
const createdToken = ref('');
const selectedKey = ref<ApiKeyRead | null>(null);
const validationMessage = ref('');
const form = reactive({
  expiresAt: '',
  name: '',
  permissions: [] as ApiKeyPermission[],
});

const columns = [
  { key: 'name', label: '名称', minWidth: 160 },
  { key: 'key_prefix', label: '前缀', width: 140 },
  { key: 'permissions', label: '权限', minWidth: 220 },
  { key: 'expires_at', label: '过期时间', width: 180 },
  { key: 'last_used_at', label: '最后使用', width: 180 },
  { key: 'revoked_at', label: '状态', width: 120 },
  { key: 'actions', label: '操作', width: 120 },
];

const tableRows = computed(() => apiKeyStore.keys as unknown as Record<string, unknown>[]);

onMounted(async () => {
  await apiKeyStore.fetchKeys({ page: 1, pageSize: 20 });
});

async function fetchKeys(page = apiKeyStore.page, pageSize = apiKeyStore.pageSize): Promise<void> {
  await apiKeyStore.fetchKeys({ page, pageSize });
}

function openCreateDialog(): void {
  form.expiresAt = '';
  form.name = '';
  form.permissions = [];
  createdToken.value = '';
  validationMessage.value = '';
  createDialogVisible.value = true;
}

function togglePermission(permission: ApiKeyPermission, checked: boolean): void {
  form.permissions = checked
    ? [...form.permissions, permission]
    : form.permissions.filter((item) => item !== permission);
}

async function submitCreate(): Promise<void> {
  validationMessage.value = validateForm();
  if (validationMessage.value) {
    return;
  }
  const result = await apiKeyStore.createKey({
    expiresAt: formatExpiresAt(form.expiresAt),
    name: form.name.trim(),
    permissions: form.permissions,
  });
  createdToken.value = result.token;
  ElMessage.success('API Key 已创建');
}

function openRevokeDialog(apiKey: ApiKeyRead): void {
  selectedKey.value = apiKey;
  revokeDialogVisible.value = true;
}

async function submitRevoke(): Promise<void> {
  if (!selectedKey.value) {
    return;
  }
  await apiKeyStore.revokeKey(selectedKey.value.id);
  revokeDialogVisible.value = false;
  ElMessage.success('API Key 已吊销');
}

function validateForm(): string {
  if (!form.name.trim()) {
    return '请输入名称';
  }
  if (!form.permissions.length) {
    return '请选择至少一个权限';
  }
  return '';
}

function formatExpiresAt(value: string): string | null {
  if (!value) {
    return null;
  }
  return new Date(value).toISOString();
}

function formatDate(value: unknown): string {
  return typeof value === 'string' ? value.replace('T', ' ').slice(0, 16) : '-';
}

function permissionLabels(permissions: unknown): string {
  if (!Array.isArray(permissions)) {
    return '-';
  }
  return permissions
    .map((permission) => {
      const option = API_KEY_PERMISSION_OPTIONS.find((item) => item.value === permission);
      return option?.label ?? String(permission);
    })
    .join('、');
}

function statusOf(apiKey: ApiKeyRead): string {
  return apiKey.revoked_at ? 'revoked' : 'active';
}
</script>

<template>
  <section class="admin-page api-key-page">
    <div class="admin-page__header">
      <div>
        <h2>API Key 管理</h2>
        <p>签发外部只读 API 凭据，控制权限范围、有效期和吊销状态。</p>
      </div>
      <el-button data-test="create-api-key" type="primary" @click="openCreateDialog">
        创建 API Key
      </el-button>
    </div>

    <DataTable
      class="admin-page__table"
      :columns="columns"
      :loading="apiKeyStore.loading"
      :page="apiKeyStore.page"
      :page-size="apiKeyStore.pageSize"
      :rows="tableRows"
      :total="apiKeyStore.total"
      @update:page="fetchKeys($event, apiKeyStore.pageSize)"
      @update:page-size="fetchKeys(1, $event)"
    >
      <template #permissions="{ value }">
        {{ permissionLabels(value) }}
      </template>
      <template #expires_at="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #last_used_at="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #revoked_at="{ row }">
        <StatusTag :status="statusOf(row as ApiKeyRead)" />
      </template>
      <template #actions="{ row }">
        <el-button
          v-if="!(row as ApiKeyRead).revoked_at"
          data-test="revoke-api-key"
          size="small"
          type="danger"
          @click="openRevokeDialog(row as ApiKeyRead)"
        >
          吊销
        </el-button>
      </template>
    </DataTable>

    <el-dialog v-model="createDialogVisible" title="创建 API Key" width="520px">
      <el-form label-width="96px">
        <el-form-item label="名称">
          <el-input v-model="form.name" data-test="api-key-name" maxlength="120" />
        </el-form-item>
        <el-form-item label="过期时间">
          <el-input v-model="form.expiresAt" data-test="api-key-expires-at" type="datetime-local" />
        </el-form-item>
        <el-form-item label="权限">
          <div class="api-key-permissions">
            <el-checkbox
              v-for="permission in API_KEY_PERMISSION_OPTIONS"
              :key="permission.value"
              :data-test="`api-key-permission-${permission.value.split(':')[0]}`"
              :label="permission.label"
              :model-value="form.permissions.includes(permission.value)"
              @update:model-value="togglePermission(permission.value, Boolean($event))"
            />
          </div>
        </el-form-item>
      </el-form>
      <p v-if="validationMessage" class="form-error">{{ validationMessage }}</p>
      <section v-if="createdToken" data-test="created-api-key-token" class="api-key-token">
        <span>请立即保存：</span>
        <code>{{ createdToken }}</code>
      </section>
      <template #footer>
        <el-button @click="createDialogVisible = false">关闭</el-button>
        <el-button
          data-test="submit-api-key"
          :loading="apiKeyStore.submitting"
          type="primary"
          @click="submitCreate"
        >
          创建
        </el-button>
      </template>
    </el-dialog>

    <ConfirmDialog
      v-model="revokeDialogVisible"
      confirm-text="吊销"
      message="吊销后该 API Key 会立即失效，外部请求将被拒绝。"
      title="吊销 API Key"
      type="danger"
      @confirm="submitRevoke"
    />
  </section>
</template>

<style scoped>
.api-key-permissions {
  display: grid;
  gap: 8px;
}

.api-key-token {
  background: #f8fafc;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  display: grid;
  gap: 8px;
  margin-top: 12px;
  padding: 12px;
}

.api-key-token code {
  color: #0f172a;
  overflow-wrap: anywhere;
}
</style>
