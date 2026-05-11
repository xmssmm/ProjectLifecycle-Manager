<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import { ConfirmDialog, DataTable, StatusTag } from '@/components/common';
import { useArchiveStore } from '@/stores/useArchiveStore';
import { useAuthStore } from '@/stores/useAuthStore';
import type {
  ArchiveBatchRead,
  ArchiveMainProjectRead,
  ArchiveSubProjectRead,
} from '@/types/archives';
import { formatUserDateTime } from '@/utils/timezone';

const archiveStore = useArchiveStore();
const authStore = useAuthStore();

const detailDialogVisible = ref(false);
const restoreDialogVisible = ref(false);
const selectedArchiveMainProject = ref<ArchiveMainProjectRead | null>(null);

const candidateColumns = [
  { key: 'project_no', label: '项目编号', minWidth: 160 },
  { key: 'name', label: '项目名称', minWidth: 180 },
  { key: 'closed_at', label: '结项时间', width: 180 },
  { key: 'sub_project_count', label: '子项目数', width: 120 },
];

const batchColumns = [
  { key: 'batch_no', label: '批次号', minWidth: 220 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'archived_main_project_count', label: '主项目', width: 110 },
  { key: 'archived_sub_project_count', label: '子项目', width: 110 },
  { key: 'duration_ms', label: '耗时', width: 110 },
  { key: 'created_at', label: '创建时间', width: 180 },
  { key: 'actions', label: '操作', width: 120 },
];

const archivedMainColumns = [
  { key: 'project_no', label: '项目编号', minWidth: 160 },
  { key: 'name', label: '项目名称', minWidth: 180 },
  { key: 'status', label: '归档状态', width: 120 },
  { key: 'closed_at', label: '结项时间', width: 180 },
  { key: 'archived_at', label: '归档时间', width: 180 },
  { key: 'actions', label: '操作', width: 120 },
];

const archivedSubColumns = [
  { key: 'project_no', label: '子项目编号', minWidth: 180 },
  { key: 'name', label: '子项目名称', minWidth: 180 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'closed_at', label: '结项时间', width: 180 },
];

const candidateRows = computed(
  () => archiveStore.candidates as unknown as Record<string, unknown>[],
);
const batchRows = computed(() => archiveStore.batches as unknown as Record<string, unknown>[]);
const archivedMainRows = computed(
  () => (archiveStore.detail?.main_projects ?? []) as unknown as Record<string, unknown>[],
);
const archivedSubRows = computed(
  () => (archiveStore.detail?.sub_projects ?? []) as unknown as Record<string, unknown>[],
);
const detailTitle = computed(() =>
  archiveStore.detail ? `归档批次 ${archiveStore.detail.batch.batch_no}` : '归档批次',
);
const restoreMessage = computed(() => {
  const archive = selectedArchiveMainProject.value;
  if (!archive) {
    return '确认恢复归档主项目？';
  }
  const subCount = subProjectsForMain(archive).length;
  return `确认恢复 ${archive.project_no}，包含 ${subCount} 个子项目快照。`;
});

onMounted(async () => {
  await Promise.all([
    archiveStore.fetchCandidates(),
    archiveStore.fetchBatches({ page: 1, pageSize: 20 }),
  ]);
});

async function fetchBatches(page = archiveStore.page, pageSize = archiveStore.pageSize) {
  await archiveStore.fetchBatches({ page, pageSize });
}

async function createBatch(): Promise<void> {
  if (archiveStore.submitting) {
    return;
  }
  const result = await archiveStore.createBatch();
  ElMessage.success(`归档批次 ${result.batch_no} 已创建`);
}

async function openBatchDetail(batch: ArchiveBatchRead): Promise<void> {
  await archiveStore.fetchBatchDetail(batch.id);
  detailDialogVisible.value = true;
}

function openRestoreDialog(archive: ArchiveMainProjectRead): void {
  selectedArchiveMainProject.value = archive;
  restoreDialogVisible.value = true;
}

async function submitRestore(): Promise<void> {
  if (!selectedArchiveMainProject.value || archiveStore.submitting) {
    return;
  }
  await archiveStore.restoreMainProject(selectedArchiveMainProject.value);
  restoreDialogVisible.value = false;
  ElMessage.success('主项目已恢复');
}

function subProjectsForMain(archive: ArchiveMainProjectRead): ArchiveSubProjectRead[] {
  return (archiveStore.detail?.sub_projects ?? []).filter(
    (item) => item.original_main_project_id === archive.original_id,
  );
}

function formatDate(value: unknown): string {
  return typeof value === 'string' ? formatUserDateTime(value, authStore.user?.timezone) : '-';
}

function formatDuration(value: unknown): string {
  if (typeof value !== 'number') {
    return '-';
  }
  return `${value} ms`;
}

function statusOf(row: ArchiveBatchRead | ArchiveMainProjectRead | ArchiveSubProjectRead): string {
  return row.status;
}
</script>

<template>
  <section class="admin-page archive-page">
    <div class="admin-page__header">
      <div>
        <h2>归档管理</h2>
        <p>查看归档候选、创建归档批次、检查历史批次并恢复归档主项目。</p>
      </div>
      <el-button
        data-test="create-archive-batch"
        :loading="archiveStore.submitting"
        type="primary"
        @click="createBatch"
      >
        创建归档批次
      </el-button>
    </div>

    <DataTable
      class="admin-page__table"
      :columns="candidateColumns"
      :loading="archiveStore.loading"
      :page="1"
      :page-size="archiveStore.candidates.length || 20"
      :rows="candidateRows"
      :total="archiveStore.candidates.length"
    >
      <template #closed_at="{ value }">
        {{ formatDate(value) }}
      </template>
    </DataTable>

    <section class="archive-page__section">
      <h3>归档批次</h3>
      <DataTable
        :columns="batchColumns"
        :loading="archiveStore.loading"
        :page="archiveStore.page"
        :page-size="archiveStore.pageSize"
        :rows="batchRows"
        :total="archiveStore.total"
        @update:page="fetchBatches($event, archiveStore.pageSize)"
        @update:page-size="fetchBatches(1, $event)"
      >
        <template #status="{ row }">
          <StatusTag :status="statusOf(row as ArchiveBatchRead)" />
        </template>
        <template #duration_ms="{ value }">
          {{ formatDuration(value) }}
        </template>
        <template #created_at="{ value }">
          {{ formatDate(value) }}
        </template>
        <template #actions="{ row }">
          <el-button
            data-test="view-archive-batch"
            size="small"
            type="primary"
            @click="openBatchDetail(row as ArchiveBatchRead)"
          >
            查看
          </el-button>
        </template>
      </DataTable>
    </section>

    <el-dialog v-model="detailDialogVisible" :title="detailTitle" width="920px">
      <DataTable
        :columns="archivedMainColumns"
        :loading="archiveStore.loading"
        :page="1"
        :page-size="archiveStore.detail?.main_projects.length || 20"
        :rows="archivedMainRows"
        :total="archiveStore.detail?.main_projects.length ?? 0"
      >
        <template #status="{ row }">
          <StatusTag :status="statusOf(row as ArchiveMainProjectRead)" />
        </template>
        <template #closed_at="{ value }">
          {{ formatDate(value) }}
        </template>
        <template #archived_at="{ value }">
          {{ formatDate(value) }}
        </template>
        <template #actions="{ row }">
          <el-button
            data-test="restore-archive-main"
            size="small"
            type="warning"
            @click="openRestoreDialog(row as ArchiveMainProjectRead)"
          >
            恢复
          </el-button>
        </template>
      </DataTable>

      <section class="archive-page__section">
        <h3>子项目快照</h3>
        <DataTable
          :columns="archivedSubColumns"
          :loading="archiveStore.loading"
          :page="1"
          :page-size="archiveStore.detail?.sub_projects.length || 20"
          :rows="archivedSubRows"
          :total="archiveStore.detail?.sub_projects.length ?? 0"
        >
          <template #status="{ row }">
            <StatusTag :status="statusOf(row as ArchiveSubProjectRead)" />
          </template>
          <template #closed_at="{ value }">
            {{ formatDate(value) }}
          </template>
        </DataTable>
      </section>
    </el-dialog>

    <ConfirmDialog
      v-model="restoreDialogVisible"
      confirm-data-test="confirm-restore-archive-main"
      confirm-text="恢复"
      :message="restoreMessage"
      title="恢复归档主项目"
      type="warning"
      @confirm="submitRestore"
    />
  </section>
</template>

<style scoped>
.archive-page__section {
  margin-top: 24px;
}

.archive-page__section h3 {
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 12px;
}
</style>
