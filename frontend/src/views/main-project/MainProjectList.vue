<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { DataTable, SearchBar, StatusTag } from '@/components/common';
import { useMainProjectStore } from '@/stores/useMainProjectStore';
import {
  MAIN_PROJECT_STATUS_OPTIONS,
  PROJECT_STATUS_LABELS,
  type MainProjectRead,
  type ProjectStatus,
} from '@/types/projects';

const mainProjectStore = useMainProjectStore();
const searchModel = ref<Record<string, string | number>>({ dept_id: '', status: '' });
const filters = ref({ deptId: '', status: '' });

const columns = [
  { key: 'project_no', label: '项目编号', minWidth: 160 },
  { key: 'name', label: '项目名称', minWidth: 220 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'dept_id', label: '部门', minWidth: 180 },
  { key: 'total_budget', label: '总预算', width: 140 },
  { key: 'expected_finish_date', label: '预计完成', width: 140 },
  { key: 'actions', label: '操作', width: 120 },
];

const searchFields = [
  {
    key: 'status',
    label: '状态',
    options: [...MAIN_PROJECT_STATUS_OPTIONS],
    placeholder: '全部状态',
    type: 'select' as const,
  },
  {
    key: 'dept_id',
    label: '部门',
    placeholder: '输入部门 ID',
    type: 'text' as const,
  },
];

const filteredProjects = computed(() =>
  mainProjectStore.projects.filter((project) => {
    const statusMatched = !filters.value.status || project.status === filters.value.status;
    const deptMatched = !filters.value.deptId || project.dept_id.includes(filters.value.deptId);
    return statusMatched && deptMatched;
  }),
);

const tableRows = computed(() => filteredProjects.value as unknown as Record<string, unknown>[]);

onMounted(async () => {
  await mainProjectStore.fetchMainProjects({ page: 1, pageSize: 20 });
});

function searchProjects(value: Record<string, string | number>): void {
  filters.value = {
    deptId: String(value.dept_id ?? '').trim(),
    status: String(value.status ?? ''),
  };
}

function resetSearch(): void {
  filters.value = { deptId: '', status: '' };
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
        <h2>主项目</h2>
        <p>按状态和部门筛选项目，进入详情查看状态和子项目。</p>
      </div>
    </div>

    <SearchBar
      v-model="searchModel"
      :fields="searchFields"
      @reset="resetSearch"
      @search="searchProjects"
    />

    <DataTable
      class="admin-page__table"
      :columns="columns"
      :loading="mainProjectStore.loading"
      :page="mainProjectStore.page"
      :page-size="mainProjectStore.pageSize"
      :rows="tableRows"
      :total="filteredProjects.length"
      @update:page="mainProjectStore.fetchMainProjects({ page: $event, pageSize: 20 })"
      @update:page-size="mainProjectStore.fetchMainProjects({ page: 1, pageSize: $event })"
    >
      <template #status="{ value }">
        <StatusTag :status="String(value)" />
      </template>
      <template #total_budget="{ value }">
        {{ formatMoney(value) }}
      </template>
      <template #expected_finish_date="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #actions="{ row }">
        <router-link
          v-if="(row as MainProjectRead | undefined)?.id"
          :to="{ name: 'main-project-detail', params: { id: (row as MainProjectRead).id } }"
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
