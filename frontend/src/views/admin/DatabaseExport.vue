<script setup lang="ts">
import { Download, Refresh, Upload } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed } from 'vue';

import { useDatabaseExportStore } from '@/stores/useDatabaseExportStore';
import { DATABASE_EXPORT_STATUS_LABELS } from '@/types/exports';
import type { DatabaseExportJobRead } from '@/types/exports';
import { formatUserDateTime } from '@/utils/timezone';
import { useAuthStore } from '@/stores/useAuthStore';

const exportStore = useDatabaseExportStore();
const authStore = useAuthStore();

const job = computed(() => exportStore.job);
const canDownload = computed(() => Boolean(job.value?.download_url && job.value.status === 'completed'));

async function createExport(): Promise<void> {
  const created = await exportStore.createJob();
  ElMessage.success(`导出任务 ${created.id} 已创建`);
}

async function refreshExport(): Promise<void> {
  const refreshed = await exportStore.refreshJob();
  if (refreshed) {
    ElMessage.success('导出任务状态已刷新');
  }
}

async function downloadExport(): Promise<void> {
  if (!job.value || !canDownload.value) {
    return;
  }
  const blob = await exportStore.downloadJob(job.value.id);
  if (!blob) {
    return;
  }
  triggerBlobDownload(blob, 'database_export.zip');
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function statusLabel(value: DatabaseExportJobRead['status']): string {
  return DATABASE_EXPORT_STATUS_LABELS[value];
}

function statusType(value: DatabaseExportJobRead['status']): string {
  if (value === 'completed') {
    return 'success';
  }
  if (value === 'failed') {
    return 'danger';
  }
  return 'warning';
}

function formatDate(value: string | null): string {
  return value ? formatUserDateTime(value, authStore.user?.timezone) : '-';
}
</script>

<template>
  <section class="admin-page database-export-page">
    <div class="admin-page__header">
      <div>
        <h2>数据库全量导出</h2>
        <p>生成包含 CSV、Excel、manifest、外键说明和审计信息的全库导出包。</p>
      </div>
      <el-button
        data-test="create-database-export"
        :icon="Upload"
        :loading="exportStore.submitting"
        type="primary"
        @click="createExport"
      >
        发起导出
      </el-button>
    </div>

    <section v-if="job" class="database-export-page__panel">
      <div class="database-export-page__toolbar">
        <el-button
          data-test="refresh-database-export"
          :icon="Refresh"
          :loading="exportStore.loading"
          @click="refreshExport"
        >
          刷新状态
        </el-button>
        <el-button
          data-test="download-database-export"
          :disabled="!canDownload"
          :icon="Download"
          :loading="exportStore.downloading"
          type="success"
          @click="downloadExport"
        >
          下载导出包
        </el-button>
      </div>

      <div class="database-export-page__summary">
        <div>
          <span>任务 ID</span>
          <strong>{{ job.id }}</strong>
        </div>
        <div>
          <span>状态</span>
          <strong>
            <el-tag :type="statusType(job.status)">{{ statusLabel(job.status) }}</el-tag>
          </strong>
        </div>
        <div>
          <span>表数量</span>
          <strong>{{ job.table_count }}</strong>
        </div>
        <div>
          <span>行数量</span>
          <strong>{{ job.row_count }}</strong>
        </div>
        <div>
          <span>完成时间</span>
          <strong>{{ formatDate(job.finished_at) }}</strong>
        </div>
      </div>

      <el-progress :percentage="job.progress" />

      <p v-if="job.error_message" class="database-export-page__error">
        {{ job.error_message }}
      </p>
    </section>
  </section>
</template>

<style scoped>
.database-export-page__panel {
  background: #fff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 18px;
}

.database-export-page__toolbar {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-bottom: 18px;
}

.database-export-page__summary {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  margin-bottom: 18px;
}

.database-export-page__summary div {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  min-width: 0;
  padding: 14px;
}

.database-export-page__summary span {
  color: #64748b;
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
}

.database-export-page__summary strong {
  color: #0f172a;
  display: block;
  font-size: 16px;
  overflow-wrap: anywhere;
}

.database-export-page__error {
  color: #b91c1c;
  margin: 16px 0 0;
}

@media (width <= 900px) {
  .database-export-page__toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .database-export-page__summary {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
