<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { DataTable, SearchBar, StatusTag } from '@/components/common';
import { usePermission } from '@/composables/usePermission';
import { useSubProjectStore } from '@/stores/useSubProjectStore';
import {
  PROJECT_STATUS_LABELS,
  SUB_PROJECT_STATUS_OPTIONS,
  type ProjectStatus,
  type SubProjectRead,
} from '@/types/projects';

const subProjectStore = useSubProjectStore();
const { can } = usePermission();
const searchModel = ref<Record<string, string | number>>({ main_project_id: '', status: '' });
const filters = ref({ mainProjectId: '', status: '' });
const canCreateSubProject = computed(() => can('sub_project.create'));

const columns = [
  { key: 'project_no', label: '子项目编号', minWidth: 180 },
  { key: 'name', label: '子项目名称', minWidth: 220 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'main_project_name', label: '主项目', minWidth: 180 },
  { key: 'dept_name', label: '责任部门', minWidth: 140 },
  { key: 'manager_name', label: '负责人', width: 120 },
  { key: 'budget', label: '预算', width: 140 },
  { key: 'spent_amount', label: '已用金额', width: 140 },
  { key: 'remaining_amount', label: '剩余额度', width: 140 },
  { key: 'plan_end_date', label: '计划完成', width: 140 },
  { key: 'actions', label: '操作', width: 120 },
];

const searchFields = [
  {
    key: 'status',
    label: '状态',
    options: [...SUB_PROJECT_STATUS_OPTIONS],
    placeholder: '全部状态',
    type: 'select' as const,
  },
  {
    key: 'main_project_id',
    label: '主项目',
    placeholder: '输入主项目名称 / ID',
    type: 'text' as const,
  },
];

const filteredSubProjects = computed(() =>
  subProjectStore.subProjects.filter((subProject) => {
    const statusMatched = !filters.value.status || subProject.status === filters.value.status;
    const mainProjectText =
      `${subProject.main_project_name ?? ''} ${subProject.main_project_id}`.toLowerCase();
    const mainProjectMatched =
      !filters.value.mainProjectId ||
      mainProjectText.includes(filters.value.mainProjectId.toLowerCase());
    return statusMatched && mainProjectMatched;
  }),
);

const tableRows = computed(() => filteredSubProjects.value as unknown as Record<string, unknown>[]);

onMounted(async () => {
  await subProjectStore.fetchSubProjects({ page: 1, pageSize: 20 });
});

function searchSubProjects(value: Record<string, string | number>): void {
  filters.value = {
    mainProjectId: String(value.main_project_id ?? '').trim(),
    status: String(value.status ?? ''),
  };
}

function resetSearch(): void {
  filters.value = { mainProjectId: '', status: '' };
}

function formatMoney(value: unknown): string {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount)
    ? amount.toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
    : '-';
}

function formatDate(value: unknown): string {
  return typeof value === 'string' && value ? value.slice(0, 10) : '-';
}

function statusLabel(status: ProjectStatus): string {
  return PROJECT_STATUS_LABELS[status];
}
</script>

<template>
  <section class="admin-page project-page">
    <div class="admin-page__header">
      <div>
        <h2>子项目</h2>
        <p>查看子项目进度、预算和审核状态。</p>
      </div>
      <router-link v-if="canCreateSubProject" :to="{ name: 'sub-project-create' }">
        <el-button type="primary">新建子项目</el-button>
      </router-link>
    </div>

    <SearchBar
      v-model="searchModel"
      :fields="searchFields"
      @reset="resetSearch"
      @search="searchSubProjects"
    />

    <DataTable
      class="admin-page__table"
      :columns="columns"
      :loading="subProjectStore.loading"
      :page="subProjectStore.page"
      :page-size="subProjectStore.pageSize"
      :rows="tableRows"
      :total="filteredSubProjects.length"
      @update:page="subProjectStore.fetchSubProjects({ page: $event, pageSize: 20 })"
      @update:page-size="subProjectStore.fetchSubProjects({ page: 1, pageSize: $event })"
    >
      <template #status="{ value }">
        <StatusTag :status="String(value)" />
      </template>
      <template #main_project_name="{ row }">
        {{ (row as SubProjectRead).main_project_name || (row as SubProjectRead).main_project_id }}
      </template>
      <template #dept_name="{ row }">
        {{ (row as SubProjectRead).dept_name || (row as SubProjectRead).dept_id }}
      </template>
      <template #manager_name="{ row }">
        {{ (row as SubProjectRead).manager_name || (row as SubProjectRead).manager_id }}
      </template>
      <template #budget="{ value }">
        {{ formatMoney(value) }}
      </template>
      <template #spent_amount="{ value }">
        {{ formatMoney(value) }}
      </template>
      <template #remaining_amount="{ value }">
        {{ formatMoney(value) }}
      </template>
      <template #plan_end_date="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #actions="{ row }">
        <router-link
          v-if="(row as SubProjectRead | undefined)?.id"
          :to="{ name: 'sub-project-detail', params: { id: (row as SubProjectRead).id } }"
        >
          <el-button size="small">查看</el-button>
        </router-link>
      </template>
    </DataTable>

    <p class="sr-only">
      当前筛选状态：{{ filters.status ? statusLabel(filters.status as ProjectStatus) : '全部' }}
    </p>
  </section>
</template>
