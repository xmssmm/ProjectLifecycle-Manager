<script setup lang="ts">
import { Check, Close, RefreshRight, UploadFilled } from '@element-plus/icons-vue';
import { computed, ref } from 'vue';

import {
  confirmDocumentType,
  suggestDocumentType,
  type DocumentTypeSuggestion,
} from '@/api/documentClassification';
import { uploadDocument } from '@/api/documents';
import {
  DOCUMENT_MAX_UPLOAD_BYTES,
  type DocumentRead,
  type DocumentUploadPayload,
} from '@/types/documents';
import { documentLabel } from '@/utils/documentLabels';

const props = withDefaults(
  defineProps<{
    acceptanceStepId?: string | null;
    docType: string;
    maxFileSizeBytes?: number;
    phaseId: string;
    subProjectId: string;
  }>(),
  {
    acceptanceStepId: null,
    maxFileSizeBytes: DOCUMENT_MAX_UPLOAD_BYTES,
  },
);

const emit = defineEmits<{
  error: [message: string];
  uploaded: [document: DocumentRead];
}>();

const displayName = ref('');
const errorMessage = ref('');
const isDragging = ref(false);
const lastFile = ref<File | null>(null);
const pendingFile = ref<File | null>(null);
const progress = ref(0);
const suggestedType = ref<DocumentTypeSuggestion | null>(null);
const suggesting = ref(false);
const uploading = ref(false);
const allowedFileExtensions = new Set([
  '.jpg',
  '.png',
  '.bmp',
  '.jpeg',
  '.doc',
  '.docx',
  '.pdf',
  '.xls',
  '.xlsx',
  '.zip',
  '.rar',
  '.7z',
]);
const acceptedFileTypes = [...allowedFileExtensions].join(',');
const uploadFormatError =
  '文件上传格式不对，请上传 .jpg .png .bmp .jpeg .doc .docx .pdf .xls .xlsx .zip .rar .7z 格式文件！';

const hasRetry = computed(() => Boolean(errorMessage.value && lastFile.value && !uploading.value));
const hasSuggestion = computed(() =>
  Boolean(suggestedType.value && pendingFile.value && !uploading.value),
);

async function handleDrop(event: DragEvent): Promise<void> {
  isDragging.value = false;
  const files = event.dataTransfer?.files;
  await startUploadFiles(Array.from(files ?? []));
}

async function handleFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  await startUploadFiles(Array.from(input.files ?? []));
  input.value = '';
}

async function retryUpload(): Promise<void> {
  if (lastFile.value) {
    await startUpload(lastFile.value);
  }
}

async function startUpload(file: File): Promise<void> {
  lastFile.value = file;
  pendingFile.value = null;
  suggestedType.value = null;
  errorMessage.value = '';
  progress.value = 0;

  const validationError = validateFile(file);
  if (validationError) {
    errorMessage.value = validationError;
    emit('error', validationError);
    return;
  }

  const suggestion = await loadSuggestion(file);
  if (suggestion && suggestion.doc_type !== props.docType) {
    pendingFile.value = file;
    suggestedType.value = suggestion;
    return;
  }

  await uploadFile(file, props.docType);
}

async function startUploadFiles(files: File[]): Promise<void> {
  for (const file of files) {
    await startUpload(file);
  }
}

async function loadSuggestion(file: File): Promise<DocumentTypeSuggestion | null> {
  suggesting.value = true;
  try {
    const result = await suggestDocumentType({
      currentDocType: props.docType,
      fileName: file.name,
      phaseId: props.phaseId,
      subProjectId: props.subProjectId,
    });
    return result.suggestions[0] ?? null;
  } catch {
    return null;
  } finally {
    suggesting.value = false;
  }
}

async function confirmSuggestedType(): Promise<void> {
  if (!pendingFile.value || !suggestedType.value) {
    return;
  }
  const file = pendingFile.value;
  const docType = suggestedType.value.doc_type;
  pendingFile.value = null;
  suggestedType.value = null;
  await uploadFile(file, docType, true);
}

async function ignoreSuggestedType(): Promise<void> {
  if (!pendingFile.value) {
    return;
  }
  const file = pendingFile.value;
  pendingFile.value = null;
  suggestedType.value = null;
  await uploadFile(file, props.docType);
}

async function uploadFile(file: File, docType: string, auditConfirmation = false): Promise<void> {
  uploading.value = true;
  try {
    const payload: DocumentUploadPayload = {
      acceptanceStepId: props.acceptanceStepId,
      displayName: displayName.value.trim() || file.name,
      docType,
      file,
      phaseId: props.phaseId,
      subProjectId: props.subProjectId,
    };
    const document = await uploadDocument(payload, undefined, (percentage) => {
      progress.value = percentage;
    });
    progress.value = 100;
    const confirmedDocument = auditConfirmation
      ? await confirmDocumentType(document.id, docType).catch(() => document)
      : document;
    displayName.value = '';
    lastFile.value = null;
    progress.value = 0;
    emit('uploaded', confirmedDocument);
  } catch (error) {
    const message = extractUploadError(error);
    errorMessage.value = message;
    emit('error', message);
  } finally {
    uploading.value = false;
  }
}

function validateFile(file: File): string {
  if (file.size > props.maxFileSizeBytes) {
    return `文件大小超过 ${formatFileSize(props.maxFileSizeBytes)} 上限`;
  }
  if (!allowedFileExtensions.has(fileExtension(file.name))) {
    return uploadFormatError;
  }
  return '';
}

function extractUploadError(error: unknown): string {
  const response = (error as { response?: { data?: unknown } }).response;
  const data = response?.data as { data?: Record<string, unknown>; message?: string } | undefined;
  const rejectionMessage = data?.data?.rejection_message;
  if (typeof rejectionMessage === 'string' && rejectionMessage) {
    return rejectionMessage;
  }
  const reason = data?.data?.rejection_reason;
  if (typeof reason === 'string' && reason) {
    return reason;
  }
  if (typeof data?.message === 'string' && data.message) {
    return data.message;
  }
  return '上传失败';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)}KB`;
  }
  return `${Math.round(bytes / 1024 / 1024)}MB`;
}

function fileExtension(fileName: string): string {
  const dotIndex = fileName.lastIndexOf('.');
  return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : '';
}
</script>

<template>
  <div class="document-uploader">
    <el-input
      v-model="displayName"
      data-test="document-display-name"
      placeholder="文件标题，例如：主合同扫描件"
    />

    <label
      class="document-uploader__drop-zone"
      :class="{ 'document-uploader__drop-zone--active': isDragging }"
      data-test="document-drop-zone"
      @dragenter.prevent="isDragging = true"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <!-- prettier-ignore -->
      <input class="sr-only" :accept="acceptedFileTypes" data-test="document-file-input" multiple type="file" @change="handleFileChange">
      <UploadFilled class="document-uploader__icon" />
      <span class="document-uploader__title">{{ documentLabel(docType) }}</span>
      <span v-if="suggesting" class="document-uploader__meta">正在识别文档类型...</span>
      <span class="document-uploader__meta">{{ lastFile?.name ?? '选择或拖入文件' }}</span>
    </label>

    <section
      v-if="hasSuggestion && suggestedType"
      class="document-uploader__suggestion"
      data-test="document-type-suggestion"
    >
      <div>
        <strong>{{ suggestedType.doc_type }}</strong>
        <span>{{ suggestedType.reason }}</span>
      </div>
      <div class="document-uploader__suggestion-actions">
        <button data-test="confirm-document-type" type="button" @click="confirmSuggestedType">
          <Check class="document-uploader__action-icon" />
          使用建议
        </button>
        <button data-test="ignore-document-type" type="button" @click="ignoreSuggestedType">
          <Close class="document-uploader__action-icon" />
          仍按 {{ documentLabel(docType) }}
        </button>
      </div>
    </section>

    <div v-if="uploading || progress > 0" class="document-uploader__progress">
      <el-progress :percentage="progress" />
    </div>

    <el-alert
      v-if="errorMessage"
      :closable="false"
      :description="errorMessage"
      data-test="upload-error"
      show-icon
      title="上传失败"
      type="error"
    />

    <button
      v-if="hasRetry"
      class="document-uploader__retry"
      data-test="retry-upload"
      type="button"
      @click="retryUpload"
    >
      <RefreshRight class="document-uploader__retry-icon" />
      重试
    </button>
  </div>
</template>

<style scoped>
.document-uploader {
  display: grid;
  gap: 10px;
}

.document-uploader__drop-zone {
  display: grid;
  place-items: center;
  min-height: 96px;
  padding: 12px;
  border: 1px dashed #b8c3d3;
  border-radius: 8px;
  color: #475467;
  background: #f8fafc;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
}

.document-uploader__drop-zone--active {
  border-color: var(--el-color-primary);
  background: #edf3ff;
}

.document-uploader__icon {
  width: 30px;
  height: 30px;
  color: var(--el-color-primary);
}

.document-uploader__title {
  margin-top: 8px;
  color: #172033;
  font-weight: 700;
}

.document-uploader__meta {
  max-width: 100%;
  margin-top: 4px;
  overflow-wrap: anywhere;
  font-size: 13px;
}

.document-uploader__progress {
  min-height: 28px;
}

.document-uploader__suggestion {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
}

.document-uploader__suggestion strong,
.document-uploader__suggestion span {
  display: block;
}

.document-uploader__suggestion strong {
  color: #172033;
  font-size: 15px;
}

.document-uploader__suggestion span {
  margin-top: 2px;
  color: #475467;
  font-size: 13px;
}

.document-uploader__suggestion-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.document-uploader__suggestion-actions button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid #1f6feb;
  border-radius: 6px;
  color: #1f6feb;
  background: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.document-uploader__action-icon {
  width: 14px;
  height: 14px;
}

.document-uploader__retry {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: fit-content;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--el-color-primary);
  border-radius: 6px;
  color: #fff;
  background: var(--el-color-primary);
  cursor: pointer;
  font: inherit;
  font-size: 14px;
}

.document-uploader__retry-icon {
  width: 16px;
  height: 16px;
}
</style>
