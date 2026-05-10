<script setup lang="ts">
import type { DocumentRead } from '@/types/documents';

defineProps<{
  baseline: DocumentRead;
  current: DocumentRead;
}>();

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  return value ? value.replace('T', ' ').slice(0, 16) : '-';
}
</script>

<template>
  <div class="document-version-diff">
    <div class="document-version-diff__header">
      <span>版本元信息对比</span>
      <el-tag type="info">v{{ current.version }} / v{{ baseline.version }}</el-tag>
    </div>
    <dl class="document-version-diff__grid">
      <dt>文件名</dt>
      <dd>{{ current.file_name }}</dd>
      <dd>{{ baseline.file_name }}</dd>
      <dt>大小</dt>
      <dd>{{ formatFileSize(current.file_size) }}</dd>
      <dd>{{ formatFileSize(baseline.file_size) }}</dd>
      <dt>上传人</dt>
      <dd>{{ current.uploader_id }}</dd>
      <dd>{{ baseline.uploader_id }}</dd>
      <dt>上传时间</dt>
      <dd>{{ formatDate(current.created_at) }}</dd>
      <dd>{{ formatDate(baseline.created_at) }}</dd>
    </dl>
  </div>
</template>

<style scoped>
.document-version-diff {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e5e9f0;
  border-radius: 8px;
  background: #fafbfc;
}

.document-version-diff__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #344054;
  font-size: 13px;
  font-weight: 600;
}

.document-version-diff__grid {
  display: grid;
  grid-template-columns: 96px 1fr 1fr;
  margin: 0;
  border-top: 1px solid #e5e9f0;
  border-left: 1px solid #e5e9f0;
  font-size: 13px;
}

.document-version-diff__grid dt,
.document-version-diff__grid dd {
  min-width: 0;
  padding: 9px 10px;
  border-right: 1px solid #e5e9f0;
  border-bottom: 1px solid #e5e9f0;
}

.document-version-diff__grid dt {
  color: #475467;
  background: #f2f4f7;
  font-weight: 600;
}

.document-version-diff__grid dd {
  margin: 0;
  overflow-wrap: anywhere;
  background: #fff;
}
</style>
