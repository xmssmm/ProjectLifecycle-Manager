<script setup lang="ts">
import { Download, Upload } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, ref } from 'vue';

import { DataTable, StatusTag } from '@/components/common';
import { useProjectImportStore } from '@/stores/useProjectImportStore';
import type {
  ProjectImportCreatedProjectRead,
  ProjectImportRowErrorRead,
} from '@/types/imports';

const importStore = useProjectImportStore();
const selectedFile = ref<File | null>(null);

const errorColumns = [
  { key: 'row_number', label: '行号', width: 90 },
  { key: 'field', label: '字段', width: 150 },
  { key: 'message', label: '错误', minWidth: 220 },
  { key: 'value', label: '原始值', minWidth: 180 },
];

const createdColumns = [
  { key: 'project_no', label: '项目编号', minWidth: 160 },
  { key: 'name', label: '项目名称', minWidth: 200 },
  { key: 'status', label: '状态', width: 120 },
];

const result = computed(() => importStore.result);
const errorRows = computed(
  () => (result.value?.errors ?? []) as unknown as Record<string, unknown>[],
);
const createdRows = computed(
  () => (result.value?.created_projects ?? []) as unknown as Record<string, unknown>[],
);
const hasResult = computed(() => result.value !== null);

function handleFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
}

async function downloadTemplate(): Promise<void> {
  const blob = await importStore.downloadTemplate();
  triggerBlobDownload(blob, 'project_import_template.xlsx');
  ElMessage.success('模板已下载');
}

async function submitImport(): Promise<void> {
  if (!selectedFile.value || importStore.submitting) {
    return;
  }
  const importResult = await importStore.importWorkbook(selectedFile.value);
  ElMessage.success(`导入批次 ${importResult.batch_no} 已完成`);
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

function statusOf(row: ProjectImportCreatedProjectRead): string {
  return row.status;
}

function errorValue(row: ProjectImportRowErrorRead): string {
  return row.value ?? '-';
}
</script>

<template>
  <section class="admin-page project-import-page">
    <div class="admin-page__header">
      <div>
        <h2>项目批量导入</h2>
        <p>下载标准 Excel 模板后上传项目清单，系统将逐行校验并返回批次结果。</p>
      </div>
      <el-button
        data-test="download-project-import-template"
        :icon="Download"
        :loading="importStore.downloading"
        @click="downloadTemplate"
      >
        下载模板
      </el-button>
    </div>

    <section class="project-import-page__panel">
      <label class="project-import-page__file">
        <input
          data-test="project-import-file"
          accept=".xlsx"
          type="file"
          @change="handleFileChange"
        >
        <span>{{ selectedFile?.name ?? '选择 Excel 文件' }}</span>
      </label>
      <el-button
        data-test="submit-project-import"
        :disabled="!selectedFile"
        :icon="Upload"
        :loading="importStore.submitting"
        type="primary"
        @click="submitImport"
      >
        开始导入
      </el-button>
    </section>

    <section v-if="hasResult && result" class="project-import-page__result">
      <div class="project-import-page__summary">
        <div>
          <span>批次号</span>
          <strong>{{ result.batch_no }}</strong>
        </div>
        <div>
          <span>总行数</span>
          <strong>{{ result.total_rows }}</strong>
        </div>
        <div>
          <span>成功</span>
          <strong>{{ result.success_count }}</strong>
        </div>
        <div>
          <span>失败</span>
          <strong>{{ result.failure_count }}</strong>
        </div>
        <div>
          <span>耗时</span>
          <strong>{{ result.duration_ms }} ms</strong>
        </div>
      </div>

      <section class="project-import-page__section">
        <h3>已创建项目</h3>
        <DataTable
          :columns="createdColumns"
          :page="1"
          :page-size="createdRows.length || 20"
          :rows="createdRows"
          :total="createdRows.length"
        >
          <template #status="{ row }">
            <StatusTag :status="statusOf(row as ProjectImportCreatedProjectRead)" />
          </template>
        </DataTable>
      </section>

      <section class="project-import-page__section">
        <h3>失败行</h3>
        <el-alert
          v-if="result.errors.length === 0"
          title="没有失败行"
          type="success"
          :closable="false"
        />
        <DataTable
          v-else
          :columns="errorColumns"
          :page="1"
          :page-size="errorRows.length || 20"
          :rows="errorRows"
          :total="errorRows.length"
        >
          <template #value="{ row }">
            {{ errorValue(row as ProjectImportRowErrorRead) }}
          </template>
        </DataTable>
      </section>
    </section>
  </section>
</template>

<style scoped>
.project-import-page__panel {
  align-items: center;
  background: #fff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  display: flex;
  gap: 16px;
  padding: 18px;
}

.project-import-page__file {
  align-items: center;
  border: 1px dashed #94a3b8;
  border-radius: 8px;
  color: #334155;
  cursor: pointer;
  display: inline-flex;
  font-size: 14px;
  min-height: 40px;
  min-width: 280px;
  padding: 0 14px;
}

.project-import-page__file input {
  inline-size: 0;
  opacity: 0;
  position: absolute;
}

.project-import-page__result {
  margin-top: 24px;
}

.project-import-page__summary {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
}

.project-import-page__summary div {
  background: #fff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  min-width: 0;
  padding: 14px;
}

.project-import-page__summary span {
  color: #64748b;
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
}

.project-import-page__summary strong {
  color: #0f172a;
  display: block;
  font-size: 16px;
  overflow-wrap: anywhere;
}

.project-import-page__section {
  margin-top: 24px;
}

.project-import-page__section h3 {
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 12px;
}

@media (width <= 900px) {
  .project-import-page__panel {
    align-items: stretch;
    flex-direction: column;
  }

  .project-import-page__file {
    min-width: 0;
    width: 100%;
  }

  .project-import-page__summary {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
