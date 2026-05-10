<script setup lang="ts">
import { ArrowLeft, ArrowRight, Download, ZoomIn, ZoomOut } from '@element-plus/icons-vue';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import * as pdfjs from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';

import { previewDocument } from '@/api/documents';
import type { DocumentRead } from '@/types/documents';

interface PdfViewport {
  height: number;
  width: number;
}

interface PdfPageProxyLike {
  getViewport(options: { scale: number }): PdfViewport;
  render(options: { canvasContext: CanvasRenderingContext2D; viewport: PdfViewport }): {
    promise: Promise<void>;
  };
}

interface PdfDocumentProxyLike {
  destroy(): Promise<void> | void;
  getPage(pageNumber: number): Promise<PdfPageProxyLike>;
  numPages: number;
}

interface PdfLoadingTaskLike {
  promise: Promise<PdfDocumentProxyLike>;
}

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const props = defineProps<{
  document: DocumentRead | null;
  loadPdf?: (blob: Blob) => Promise<PdfDocumentProxyLike>;
  modelValue: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const currentPage = ref(1);
const errorMessage = ref('');
const loading = ref(false);
const pageCount = ref(0);
const pdfDocument = ref<PdfDocumentProxyLike | null>(null);
const previewUrl = ref('');
const zoom = ref(1);

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});

const zoomLabel = computed(() => `${Math.round(zoom.value * 100)}%`);

watch(
  () => [props.modelValue, props.document?.id] as const,
  async ([isVisible]) => {
    if (!isVisible) {
      cleanupPreview();
      return;
    }
    if (props.document) {
      await loadPreview(props.document);
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  cleanupPreview();
});

async function loadPreview(document: DocumentRead): Promise<void> {
  cleanupPreview();
  loading.value = true;
  errorMessage.value = '';
  currentPage.value = 1;
  zoom.value = 1;

  try {
    const blob = await previewDocument(document.id);
    previewUrl.value = createBlobUrl(blob, document.id);
    pdfDocument.value = await (props.loadPdf ?? loadPdfWithPdfjs)(blob);
    pageCount.value = pdfDocument.value.numPages;
    await nextTick();
    await renderCurrentPage();
  } catch {
    errorMessage.value = 'PDF 预览加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadPdfWithPdfjs(blob: Blob): Promise<PdfDocumentProxyLike> {
  const task = pdfjs.getDocument({ data: await blob.arrayBuffer() }) as PdfLoadingTaskLike;
  return task.promise;
}

async function renderCurrentPage(): Promise<void> {
  if (!pdfDocument.value || !canvasRef.value) {
    return;
  }
  const page = await pdfDocument.value.getPage(currentPage.value);
  const viewport = page.getViewport({ scale: zoom.value });
  const context = safeCanvasContext(canvasRef.value);
  if (!context) {
    return;
  }
  canvasRef.value.width = viewport.width;
  canvasRef.value.height = viewport.height;
  await page.render({ canvasContext: context, viewport }).promise;
}

function safeCanvasContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
  try {
    return canvas.getContext('2d');
  } catch {
    return null;
  }
}

async function goToPreviousPage(): Promise<void> {
  if (currentPage.value <= 1) {
    return;
  }
  currentPage.value -= 1;
  await renderCurrentPage();
}

async function goToNextPage(): Promise<void> {
  if (currentPage.value >= pageCount.value) {
    return;
  }
  currentPage.value += 1;
  await renderCurrentPage();
}

async function zoomOut(): Promise<void> {
  zoom.value = Math.max(0.5, zoom.value - 0.25);
  await renderCurrentPage();
}

async function zoomIn(): Promise<void> {
  zoom.value = Math.min(2, zoom.value + 0.25);
  await renderCurrentPage();
}

function closePreview(): void {
  visible.value = false;
}

function cleanupPreview(): void {
  if (pdfDocument.value) {
    void pdfDocument.value.destroy();
  }
  pdfDocument.value = null;
  pageCount.value = 0;
  if (previewUrl.value && typeof URL.revokeObjectURL === 'function') {
    URL.revokeObjectURL(previewUrl.value);
  }
  previewUrl.value = '';
}

function createBlobUrl(blob: Blob, fallbackId: string): string {
  if (typeof URL.createObjectURL === 'function') {
    return URL.createObjectURL(blob);
  }
  return `blob:${fallbackId}`;
}
</script>

<template>
  <el-dialog
    v-model="visible"
    class="pdf-preview"
    width="min(96vw, 980px)"
    @closed="cleanupPreview"
  >
    <template #header>
      <div class="pdf-preview__title">
        <span>{{ document?.file_name ?? 'PDF 预览' }}</span>
        <small v-if="pageCount">{{ currentPage }} / {{ pageCount }}</small>
      </div>
    </template>

    <div class="pdf-preview__toolbar">
      <button
        class="pdf-preview__button"
        data-test="previous-page"
        :disabled="currentPage <= 1"
        type="button"
        @click="goToPreviousPage"
      >
        <ArrowLeft class="pdf-preview__icon" />
      </button>
      <button
        class="pdf-preview__button"
        data-test="next-page"
        :disabled="currentPage >= pageCount"
        type="button"
        @click="goToNextPage"
      >
        <ArrowRight class="pdf-preview__icon" />
      </button>
      <span class="pdf-preview__page">{{ currentPage }} / {{ pageCount || 1 }}</span>
      <button
        class="pdf-preview__button"
        data-test="zoom-out"
        :disabled="zoom <= 0.5"
        type="button"
        @click="zoomOut"
      >
        <ZoomOut class="pdf-preview__icon" />
      </button>
      <span class="pdf-preview__zoom">{{ zoomLabel }}</span>
      <button
        class="pdf-preview__button"
        data-test="zoom-in"
        :disabled="zoom >= 2"
        type="button"
        @click="zoomIn"
      >
        <ZoomIn class="pdf-preview__icon" />
      </button>
      <a
        v-if="previewUrl && document"
        class="pdf-preview__download"
        data-test="preview-download"
        :download="document.file_name"
        :href="previewUrl"
      >
        <Download class="pdf-preview__icon" />
        下载
      </a>
    </div>

    <el-alert
      v-if="errorMessage"
      :closable="false"
      :description="errorMessage"
      show-icon
      title="预览失败"
      type="error"
    />

    <div class="pdf-preview__canvas-wrap" :aria-busy="loading ? 'true' : 'false'">
      <canvas ref="canvasRef" class="pdf-preview__canvas" />
    </div>

    <template #footer>
      <button class="pdf-preview__close" type="button" @click="closePreview">关闭</button>
    </template>
  </el-dialog>
</template>

<style scoped>
.pdf-preview__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.pdf-preview__title span {
  overflow: hidden;
  color: #172033;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-preview__title small,
.pdf-preview__page,
.pdf-preview__zoom {
  color: #667085;
  font-size: 13px;
}

.pdf-preview__toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.pdf-preview__button,
.pdf-preview__download,
.pdf-preview__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 11px;
  border: 1px solid #cfd6e2;
  border-radius: 6px;
  color: #344054;
  background: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-decoration: none;
}

.pdf-preview__button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.pdf-preview__download {
  margin-left: auto;
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.pdf-preview__close {
  color: #fff;
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
}

.pdf-preview__icon {
  width: 16px;
  height: 16px;
}

.pdf-preview__canvas-wrap {
  overflow: auto;
  min-height: 360px;
  max-height: 68vh;
  border: 1px solid #d8dde5;
  border-radius: 8px;
  background: #eef2f7;
}

.pdf-preview__canvas {
  display: block;
  max-width: 100%;
  margin: 16px auto;
  background: #fff;
  box-shadow: 0 8px 24px rgb(15 23 42 / 12%);
}
</style>
