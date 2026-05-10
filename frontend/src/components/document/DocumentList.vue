<script setup lang="ts">
import { CircleCheck, Clock, Collection, Download, View, Warning } from '@element-plus/icons-vue';
import { computed, defineAsyncComponent, reactive, ref, watch } from 'vue';

import { previewDocument, previewOfficeDocument } from '@/api/documents';
import DocumentVersionDiff from '@/components/document/DocumentVersionDiff.vue';
import type { DocumentRead } from '@/types/documents';

const PdfPreview = defineAsyncComponent(() => import('@/components/document/PdfPreview.vue'));
const officePreviewExtensions = new Set(['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']);
type PreviewLoader = (documentId: string) => Promise<Blob>;

interface DocumentGroup {
  docType: string;
  documents: DocumentRead[];
  latest: DocumentRead;
}

const props = defineProps<{
  documents: DocumentRead[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  download: [document: DocumentRead];
}>();

const expandedTypes = ref<Set<string>>(new Set());
const previewTarget = ref<DocumentRead | null>(null);
const previewDownloadFileName = ref('');
const previewLoader = ref<PreviewLoader>(previewDocument);
const previewVisible = ref(false);
const selectedDocumentIds = reactive<Record<string, string>>({});

const groups = computed<DocumentGroup[]>(() => {
  const grouped = new Map<string, DocumentRead[]>();
  for (const document of props.documents) {
    const list = grouped.get(document.doc_type) ?? [];
    list.push(document);
    grouped.set(document.doc_type, list);
  }
  return [...grouped.entries()]
    .map(([docType, documents]) => {
      const sorted = [...documents].sort((left, right) => right.version - left.version);
      return { docType, documents: sorted, latest: sorted[0] };
    })
    .sort((left, right) => left.docType.localeCompare(right.docType));
});

watch(
  groups,
  (nextGroups) => {
    for (const group of nextGroups) {
      if (!selectedDocumentIds[group.docType]) {
        selectedDocumentIds[group.docType] = group.latest.id;
      }
    }
  },
  { immediate: true },
);

function selectedDocument(group: DocumentGroup): DocumentRead {
  return (
    group.documents.find((document) => document.id === selectedDocumentIds[group.docType]) ??
    group.latest
  );
}

function toggleHistory(docType: string): void {
  const nextExpanded = new Set(expandedTypes.value);
  if (nextExpanded.has(docType)) {
    nextExpanded.delete(docType);
  } else {
    nextExpanded.add(docType);
  }
  expandedTypes.value = nextExpanded;
}

function selectVersion(group: DocumentGroup, document: DocumentRead): void {
  selectedDocumentIds[group.docType] = document.id;
}

function openPreview(document: DocumentRead): void {
  previewTarget.value = document;
  previewDownloadFileName.value = document.file_name;
  previewLoader.value = previewDocument;
  previewVisible.value = true;
}

function openOfficePreview(document: DocumentRead): void {
  previewTarget.value = document;
  previewDownloadFileName.value = officePreviewPdfFileName(document.file_name);
  previewLoader.value = previewOfficeDocument;
  previewVisible.value = true;
}

function isPdfDocument(document: DocumentRead): boolean {
  return (
    document.file_name.toLowerCase().endsWith('.pdf') || document.doc_type.toLowerCase() === 'pdf'
  );
}

function isOfficeDocument(document: DocumentRead): boolean {
  return officePreviewExtensions.has(fileExtension(document.file_name));
}

function fileExtension(fileName: string): string {
  const dotIndex = fileName.lastIndexOf('.');
  return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : '';
}

function officePreviewPdfFileName(fileName: string): string {
  const dotIndex = fileName.lastIndexOf('.');
  const baseName = dotIndex >= 0 ? fileName.slice(0, dotIndex) : fileName;
  return `${baseName}.pdf`;
}

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

function scanStatusLabel(document: DocumentRead): string {
  const labels = {
    pending: '扫描中',
    clean: '已通过',
    infected: '已隔离',
    failed: '扫描失败',
  } satisfies Record<DocumentRead['scan_status'], string>;
  return labels[document.scan_status];
}

function scanStatusType(document: DocumentRead): 'danger' | 'info' | 'success' | 'warning' {
  if (document.scan_status === 'clean') {
    return 'success';
  }
  if (document.scan_status === 'infected') {
    return 'danger';
  }
  if (document.scan_status === 'failed') {
    return 'warning';
  }
  return 'info';
}

function scanStatusIcon(document: DocumentRead): typeof CircleCheck | typeof Warning {
  return document.scan_status === 'clean' ? CircleCheck : Warning;
}

function canAccessFile(document: DocumentRead): boolean {
  return document.scan_status === 'clean';
}
</script>

<template>
  <div class="document-list" :aria-busy="loading ? 'true' : 'false'">
    <el-empty v-if="groups.length === 0" description="暂无文档" />

    <section
      v-for="group in groups"
      :key="group.docType"
      class="document-list__group"
      :data-test="`document-group-${group.docType}`"
    >
      <header class="document-list__header">
        <div>
          <h3>{{ group.docType }}</h3>
          <span>{{ group.documents.length }} 个版本</span>
        </div>
        <el-tag :type="group.latest.is_deleted ? 'warning' : 'success'">
          最新 v{{ group.latest.version }}
        </el-tag>
      </header>

      <div class="document-list__selected">
        <div class="document-list__file">
          <strong>{{ selectedDocument(group).file_name }}</strong>
          <span>v{{ selectedDocument(group).version }}</span>
        </div>
        <dl class="document-list__meta">
          <div>
            <dt>大小</dt>
            <dd>{{ formatFileSize(selectedDocument(group).file_size) }}</dd>
          </div>
          <div>
            <dt>上传人</dt>
            <dd>{{ selectedDocument(group).uploader_id }}</dd>
          </div>
          <div>
            <dt>上传时间</dt>
            <dd>{{ formatDate(selectedDocument(group).created_at) }}</dd>
          </div>
          <div>
            <dt>安全扫描</dt>
            <dd>
              <el-tag
                :data-test="`scan-status-${group.docType}`"
                :type="scanStatusType(selectedDocument(group))"
              >
                <component
                  :is="scanStatusIcon(selectedDocument(group))"
                  class="document-list__scan-icon"
                />
                {{ scanStatusLabel(selectedDocument(group)) }}
              </el-tag>
            </dd>
          </div>
        </dl>
        <div class="document-list__actions">
          <button
            v-if="isPdfDocument(selectedDocument(group))"
            class="document-list__button"
            :data-test="`preview-${group.docType}`"
            :disabled="!canAccessFile(selectedDocument(group))"
            type="button"
            @click="openPreview(selectedDocument(group))"
          >
            <View class="document-list__button-icon" />
            预览
          </button>
          <button
            v-if="isOfficeDocument(selectedDocument(group))"
            class="document-list__button"
            :data-test="`preview-office-${group.docType}`"
            :disabled="!canAccessFile(selectedDocument(group))"
            type="button"
            @click="openOfficePreview(selectedDocument(group))"
          >
            <View class="document-list__button-icon" />
            Office 预览
          </button>
          <button
            class="document-list__button"
            :disabled="!canAccessFile(selectedDocument(group))"
            type="button"
            @click="emit('download', selectedDocument(group))"
          >
            <Download class="document-list__button-icon" />
            下载
          </button>
          <button
            class="document-list__button"
            :data-test="`show-history-${group.docType}`"
            type="button"
            @click="toggleHistory(group.docType)"
          >
            <Collection class="document-list__button-icon" />
            历史
          </button>
        </div>
      </div>

      <div v-if="expandedTypes.has(group.docType)" class="document-list__history">
        <button
          v-for="document in group.documents"
          :key="document.id"
          class="document-list__button"
          :class="{
            'document-list__button--active': selectedDocument(group).id === document.id,
          }"
          :data-test="`select-${group.docType}-v${document.version}`"
          type="button"
          @click="selectVersion(group, document)"
        >
          <Clock class="document-list__button-icon" />
          v{{ document.version }}
        </button>
      </div>

      <DocumentVersionDiff
        v-if="selectedDocument(group).id !== group.latest.id"
        :baseline="group.latest"
        :current="selectedDocument(group)"
      />
    </section>

    <PdfPreview
      v-model="previewVisible"
      :document="previewTarget"
      :download-file-name="previewDownloadFileName"
      :preview-loader="previewLoader"
    />
  </div>
</template>

<style scoped>
.document-list {
  display: grid;
  gap: 14px;
}

.document-list__group {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #d8dde5;
  border-radius: 8px;
  background: #fff;
}

.document-list__header,
.document-list__selected,
.document-list__actions,
.document-list__history {
  display: flex;
  align-items: center;
  gap: 12px;
}

.document-list__header {
  justify-content: space-between;
}

.document-list__header h3 {
  margin: 0;
  font-size: 16px;
}

.document-list__header span,
.document-list__file span {
  color: #667085;
  font-size: 13px;
}

.document-list__selected {
  align-items: flex-start;
  justify-content: space-between;
}

.document-list__file {
  display: grid;
  gap: 4px;
  min-width: 180px;
}

.document-list__file strong,
.document-list__meta dd {
  overflow-wrap: anywhere;
}

.document-list__meta {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin: 0;
}

.document-list__meta div {
  min-width: 0;
}

.document-list__meta dt {
  color: #667085;
  font-size: 12px;
}

.document-list__meta dd {
  margin: 4px 0 0;
  color: #344054;
  font-size: 13px;
}

.document-list__actions,
.document-list__history {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.document-list__button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid #cfd6e2;
  border-radius: 6px;
  color: #344054;
  background: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.document-list__button:disabled {
  color: #98a2b3;
  background: #f2f4f7;
  cursor: not-allowed;
}

.document-list__button--active {
  border-color: var(--el-color-primary);
  color: #fff;
  background: var(--el-color-primary);
}

.document-list__button-icon {
  width: 15px;
  height: 15px;
}

.document-list__scan-icon {
  width: 13px;
  height: 13px;
  margin-right: 4px;
  vertical-align: -2px;
}

@media (width <= 768px) {
  .document-list__header,
  .document-list__selected {
    align-items: stretch;
    flex-direction: column;
  }

  .document-list__meta {
    grid-template-columns: 1fr;
  }

  .document-list__actions,
  .document-list__history {
    justify-content: flex-start;
  }
}
</style>
