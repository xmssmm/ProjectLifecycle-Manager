<script setup lang="ts">
import { RefreshRight, UploadFilled } from '@element-plus/icons-vue';
import { computed, ref } from 'vue';

import { uploadDocument } from '@/api/documents';
import {
  DOCUMENT_MAX_UPLOAD_BYTES,
  type DocumentRead,
  type DocumentUploadPayload,
} from '@/types/documents';

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

const errorMessage = ref('');
const isDragging = ref(false);
const lastFile = ref<File | null>(null);
const progress = ref(0);
const uploading = ref(false);

const hasRetry = computed(() => Boolean(errorMessage.value && lastFile.value && !uploading.value));

async function handleDrop(event: DragEvent): Promise<void> {
  isDragging.value = false;
  const files = event.dataTransfer?.files;
  const file = files?.item?.(0) ?? files?.[0];
  if (file) {
    await startUpload(file);
  }
}

async function handleFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.item(0);
  if (file) {
    await startUpload(file);
  }
  input.value = '';
}

async function retryUpload(): Promise<void> {
  if (lastFile.value) {
    await startUpload(lastFile.value);
  }
}

async function startUpload(file: File): Promise<void> {
  lastFile.value = file;
  errorMessage.value = '';
  progress.value = 0;

  const validationError = validateFile(file);
  if (validationError) {
    errorMessage.value = validationError;
    emit('error', validationError);
    return;
  }

  uploading.value = true;
  try {
    const payload: DocumentUploadPayload = {
      acceptanceStepId: props.acceptanceStepId,
      docType: props.docType,
      file,
      phaseId: props.phaseId,
      subProjectId: props.subProjectId,
    };
    const document = await uploadDocument(payload, undefined, (percentage) => {
      progress.value = percentage;
    });
    progress.value = 100;
    emit('uploaded', document);
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
  return '';
}

function extractUploadError(error: unknown): string {
  const response = (error as { response?: { data?: unknown } }).response;
  const data = response?.data as { data?: Record<string, unknown>; message?: string } | undefined;
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
</script>

<template>
  <div class="document-uploader">
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
      <input class="sr-only" data-test="document-file-input" type="file" @change="handleFileChange">
      <UploadFilled class="document-uploader__icon" />
      <span class="document-uploader__title">{{ docType }}</span>
      <span class="document-uploader__meta">{{ lastFile?.name ?? '选择或拖入文件' }}</span>
    </label>

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
  min-height: 148px;
  padding: 18px;
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
