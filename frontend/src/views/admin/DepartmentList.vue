<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import { ConfirmDialog, DataTable, SearchBar } from '@/components/common';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDepartmentStore } from '@/stores/useDepartmentStore';
import type {
  DepartmentCreatePayload,
  DepartmentRead,
  DepartmentUpdatePayload,
} from '@/types/departments';
import { formatUserDateTime } from '@/utils/timezone';

import DepartmentEdit from './DepartmentEdit.vue';

interface ApiErrorResponse {
  code?: number;
  data?: {
    active_user_count?: number;
  };
  message?: string;
}

const departmentStore = useDepartmentStore();
const authStore = useAuthStore();
const searchModel = ref<Record<string, string | number>>({ keyword: '' });
const keyword = ref('');
const editDialogVisible = ref(false);
const deleteDialogVisible = ref(false);
const selectedDepartment = ref<DepartmentRead | null>(null);
const submitting = ref(false);

const columns = [
  { key: 'code', label: '部门编码', minWidth: 160 },
  { key: 'name', label: '部门名称', minWidth: 200 },
  { key: 'updated_at', label: '更新时间', width: 180 },
  { key: 'actions', label: '操作', width: 180 },
];

const searchFields = [
  { key: 'keyword', label: '关键字', placeholder: '编码 / 名称', type: 'text' as const },
];

const filteredDepartments = computed(() => {
  const value = keyword.value.trim().toLowerCase();
  if (!value) {
    return departmentStore.departments;
  }

  return departmentStore.departments.filter(
    (department) =>
      department.code.toLowerCase().includes(value) ||
      department.name.toLowerCase().includes(value),
  );
});

const tableRows = computed(() => filteredDepartments.value as unknown as Record<string, unknown>[]);

onMounted(async () => {
  await departmentStore.fetchDepartments();
});

function searchDepartments(value: Record<string, string | number>): void {
  keyword.value = String(value.keyword ?? '');
}

function resetSearch(): void {
  keyword.value = '';
}

function openCreateDialog(): void {
  selectedDepartment.value = null;
  editDialogVisible.value = true;
}

function openEditDialog(department: DepartmentRead): void {
  selectedDepartment.value = department;
  editDialogVisible.value = true;
}

function openDeleteDialog(department: DepartmentRead): void {
  selectedDepartment.value = department;
  deleteDialogVisible.value = true;
}

async function submitDepartment(
  payload: DepartmentCreatePayload | DepartmentUpdatePayload,
): Promise<void> {
  submitting.value = true;
  try {
    if (selectedDepartment.value) {
      await departmentStore.updateDepartment(selectedDepartment.value.id, payload);
      ElMessage.success('部门已更新');
    } else {
      await departmentStore.createDepartment(payload as DepartmentCreatePayload);
      ElMessage.success('部门已创建');
    }
    editDialogVisible.value = false;
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '保存部门失败'));
  } finally {
    submitting.value = false;
  }
}

async function submitDelete(): Promise<void> {
  if (!selectedDepartment.value) {
    return;
  }

  submitting.value = true;
  try {
    await departmentStore.deleteDepartment(selectedDepartment.value.id);
    ElMessage.success('部门已删除');
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '删除部门失败'));
  } finally {
    submitting.value = false;
  }
}

function formatDate(value: unknown): string {
  return typeof value === 'string' ? formatUserDateTime(value, authStore.user?.timezone) : '-';
}

function readErrorMessage(error: unknown, fallback: string): string {
  const response = (error as { response?: { data?: ApiErrorResponse } }).response?.data;
  if (response?.code === 3003) {
    const count = response.data?.active_user_count ?? 0;
    return `部门下仍有 ${count} 个活跃用户，不能删除`;
  }
  return response?.message ?? fallback;
}
</script>

<template>
  <section class="admin-page">
    <div class="admin-page__header">
      <div>
        <h2>部门管理</h2>
        <p>维护部门编码和名称，删除前会检查活跃用户。</p>
      </div>
      <el-button data-test="create-department" type="primary" @click="openCreateDialog">
        创建部门
      </el-button>
    </div>

    <SearchBar
      v-model="searchModel"
      :fields="searchFields"
      @reset="resetSearch"
      @search="searchDepartments"
    />

    <DataTable
      class="admin-page__table"
      :columns="columns"
      :loading="departmentStore.loading"
      :page="1"
      :page-size="20"
      :rows="tableRows"
      :total="filteredDepartments.length"
    >
      <template #updated_at="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #actions="{ row }">
        <div class="row-actions">
          <el-button
            data-test="edit-department"
            size="small"
            @click="openEditDialog(row as DepartmentRead)"
          >
            编辑
          </el-button>
          <el-button
            data-test="delete-department"
            size="small"
            type="danger"
            @click="openDeleteDialog(row as DepartmentRead)"
          >
            删除
          </el-button>
        </div>
      </template>
    </DataTable>

    <DepartmentEdit
      v-model="editDialogVisible"
      :department="selectedDepartment"
      :submitting="submitting"
      @submit="submitDepartment"
    />

    <ConfirmDialog
      v-model="deleteDialogVisible"
      confirm-text="删除"
      message="仅当部门下无活跃用户时才允许删除。"
      title="删除部门"
      type="danger"
      @confirm="submitDelete"
    />
  </section>
</template>
