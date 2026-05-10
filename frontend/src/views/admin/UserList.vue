<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import { ConfirmDialog, DataTable, SearchBar, StatusTag } from '@/components/common';
import { useUserStore } from '@/stores/useUserStore';
import type { UserRole } from '@/stores/useAuthStore';
import type {
  PasswordResetPayload,
  UserCreatePayload,
  UserRead,
  UserUpdatePayload,
} from '@/types/users';
import { ROLE_LABELS } from '@/types/users';

import UserEdit from './UserEdit.vue';

interface ApiErrorResponse {
  code?: number;
  data?: {
    in_flight_count?: number;
  };
  message?: string;
}

const userStore = useUserStore();
const searchModel = ref<Record<string, string | number>>({ keyword: '', role: '' });
const keyword = ref('');
const editDialogVisible = ref(false);
const resetDialogVisible = ref(false);
const disableDialogVisible = ref(false);
const selectedUser = ref<UserRead | null>(null);
const resetPasswordValue = ref('');
const submitting = ref(false);

const columns = [
  { key: 'username', label: '用户名', minWidth: 150 },
  { key: 'email', label: '邮箱', minWidth: 180 },
  { key: 'role', label: '角色', width: 150 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'updated_at', label: '更新时间', width: 180 },
  { key: 'actions', label: '操作', width: 260 },
];

const searchFields = [
  { key: 'keyword', label: '关键字', placeholder: '用户名 / 邮箱', type: 'text' as const },
  {
    key: 'role',
    label: '角色',
    options: [
      { label: '全部', value: '' },
      ...Object.entries(ROLE_LABELS).map(([value, label]) => ({ label, value })),
    ],
    type: 'select' as const,
  },
];

const filteredUsers = computed(() => {
  const value = keyword.value.trim().toLowerCase();
  if (!value) {
    return userStore.users;
  }

  return userStore.users.filter((user) => {
    const email = user.email ?? '';
    return user.username.toLowerCase().includes(value) || email.toLowerCase().includes(value);
  });
});

const tableRows = computed(() => filteredUsers.value as unknown as Record<string, unknown>[]);

onMounted(async () => {
  await userStore.fetchUsers({ page: 1, pageSize: 20, role: undefined });
});

function normalizeRole(value: string | number | undefined): UserRole | undefined {
  return value ? (String(value) as UserRole) : undefined;
}

async function fetchUsers(page = userStore.page, pageSize = userStore.pageSize): Promise<void> {
  await userStore.fetchUsers({
    page,
    pageSize,
    role: normalizeRole(searchModel.value.role),
  });
}

async function searchUsers(value: Record<string, string | number>): Promise<void> {
  keyword.value = String(value.keyword ?? '');
  await fetchUsers(1, userStore.pageSize);
}

async function resetSearch(): Promise<void> {
  keyword.value = '';
  await fetchUsers(1, userStore.pageSize);
}

function openCreateDialog(): void {
  selectedUser.value = null;
  editDialogVisible.value = true;
}

function openEditDialog(user: UserRead): void {
  selectedUser.value = user;
  editDialogVisible.value = true;
}

function openResetDialog(user: UserRead): void {
  selectedUser.value = user;
  resetPasswordValue.value = '';
  resetDialogVisible.value = true;
}

function openDisableDialog(user: UserRead): void {
  selectedUser.value = user;
  disableDialogVisible.value = true;
}

async function submitUser(payload: UserCreatePayload | UserUpdatePayload): Promise<void> {
  submitting.value = true;
  try {
    if (selectedUser.value) {
      await userStore.updateUser(selectedUser.value.id, payload as UserUpdatePayload);
      ElMessage.success('用户已更新');
    } else {
      await userStore.createUser(payload as UserCreatePayload);
      ElMessage.success('用户已创建');
    }
    editDialogVisible.value = false;
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '保存用户失败'));
  } finally {
    submitting.value = false;
  }
}

async function submitPasswordReset(): Promise<void> {
  if (!selectedUser.value) {
    return;
  }

  const payload: PasswordResetPayload = { new_password: resetPasswordValue.value };
  submitting.value = true;
  try {
    await userStore.resetPassword(selectedUser.value.id, payload);
    ElMessage.success('密码已重置');
    resetDialogVisible.value = false;
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '重置密码失败'));
  } finally {
    submitting.value = false;
  }
}

async function submitDisable(): Promise<void> {
  if (!selectedUser.value) {
    return;
  }

  submitting.value = true;
  try {
    await userStore.disableUser(selectedUser.value.id);
    ElMessage.success('用户已停用');
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '停用用户失败'));
  } finally {
    submitting.value = false;
  }
}

function formatDate(value: unknown): string {
  return typeof value === 'string' ? value.replace('T', ' ').slice(0, 16) : '-';
}

function readErrorMessage(error: unknown, fallback: string): string {
  const response = (error as { response?: { data?: ApiErrorResponse } }).response?.data;
  if (response?.code === 3010) {
    const count = response.data?.in_flight_count ?? 0;
    return `该负责人仍有 ${count} 个在途项目，需先完成转交`;
  }
  return response?.message ?? fallback;
}
</script>

<template>
  <section class="admin-page">
    <div class="admin-page__header">
      <div>
        <h2>用户管理</h2>
        <p>维护账号、角色、状态和密码重置。</p>
      </div>
      <el-button data-test="create-user" type="primary" @click="openCreateDialog">
        创建用户
      </el-button>
    </div>

    <SearchBar
      v-model="searchModel"
      :fields="searchFields"
      @reset="resetSearch"
      @search="searchUsers"
    />

    <DataTable
      class="admin-page__table"
      :columns="columns"
      :loading="userStore.loading"
      :page="userStore.page"
      :page-size="userStore.pageSize"
      :rows="tableRows"
      :total="userStore.total"
      @update:page="fetchUsers($event, userStore.pageSize)"
      @update:page-size="fetchUsers(1, $event)"
    >
      <template #email="{ value }">
        {{ value || '-' }}
      </template>
      <template #role="{ value }">
        {{ ROLE_LABELS[value as UserRole] }}
      </template>
      <template #status="{ value }">
        <StatusTag :status="String(value)" />
      </template>
      <template #updated_at="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #actions="{ row }">
        <div class="row-actions">
          <el-button data-test="edit-user" size="small" @click="openEditDialog(row as UserRead)">
            编辑
          </el-button>
          <el-button size="small" @click="openResetDialog(row as UserRead)">重置密码</el-button>
          <el-tooltip
            content="系统会在停用前检查在途项目；若存在未完成子项目会阻断操作。"
            placement="top"
          >
            <el-button
              data-test="disable-user"
              size="small"
              type="danger"
              @click="openDisableDialog(row as UserRead)"
            >
              停用
            </el-button>
          </el-tooltip>
        </div>
      </template>
    </DataTable>

    <UserEdit
      v-model="editDialogVisible"
      :submitting="submitting"
      :user="selectedUser"
      @submit="submitUser"
    />

    <el-dialog v-model="resetDialogVisible" title="重置密码" width="420px">
      <el-form label-width="96px">
        <el-form-item label="新密码">
          <el-input v-model="resetPasswordValue" autocomplete="new-password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button :loading="submitting" type="primary" @click="submitPasswordReset">
          保存
        </el-button>
      </template>
    </el-dialog>

    <ConfirmDialog
      v-model="disableDialogVisible"
      confirm-text="停用"
      message="停用后该用户不能继续登录，系统会同步撤销其未过期 token。"
      title="停用用户"
      type="danger"
      @confirm="submitDisable"
    />
  </section>
</template>
