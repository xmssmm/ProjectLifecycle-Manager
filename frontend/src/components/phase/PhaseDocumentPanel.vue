<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { downloadDocument, listDocuments } from '@/api/documents';
import DocumentList from '@/components/document/DocumentList.vue';
import DocumentUploader from '@/components/document/DocumentUploader.vue';
import { usePhaseStore } from '@/stores/usePhaseStore';
import type { DocumentRead } from '@/types/documents';
import type { PhaseDetailRead, PhaseRead, PhaseRequiredDocumentRead } from '@/types/phases';

const props = defineProps<{
  subProjectId: string;
}>();

const phaseStore = usePhaseStore();
const documents = ref<DocumentRead[]>([]);
const documentsLoading = ref(false);
const detail = ref<PhaseDetailRead | null>(null);
const selectedPhaseId = ref('');

const phaseOptions = computed(() =>
  phaseStore.phases
    .filter((phase) => phase.sub_project_id === props.subProjectId)
    .sort((left, right) => left.phase_no - right.phase_no),
);
const missingDocTypes = computed(() => new Set(detail.value?.completion.missing_doc_types ?? []));
const completionText = computed(() => {
  const completion = detail.value?.completion;
  if (!completion) {
    return '0 / 0';
  }
  return `${completion.uploaded_total} / ${completion.required_total}`;
});

onMounted(initialize);

watch(
  () => props.subProjectId,
  async () => {
    selectedPhaseId.value = '';
    detail.value = null;
    documents.value = [];
    await initialize();
  },
);

watch(selectedPhaseId, async (phaseId) => {
  if (phaseId) {
    await loadSelectedPhase();
  }
});

async function initialize(): Promise<void> {
  if (phaseOptions.value.length === 0) {
    await phaseStore.fetchPhases(props.subProjectId);
  }
  selectDefaultPhase();
}

function selectDefaultPhase(): void {
  const phases = phaseOptions.value;
  const preferred =
    phases.find((phase) => phase.status === 'in_progress') ??
    phases.find((phase) => phase.status === 'waiting') ??
    phases[0];
  if (preferred) {
    selectedPhaseId.value = preferred.id;
  }
}

function selectPhase(phase: PhaseRead): void {
  selectedPhaseId.value = phase.id;
}

async function loadSelectedPhase(): Promise<void> {
  const phaseId = selectedPhaseId.value;
  if (!phaseId) {
    return;
  }

  documentsLoading.value = true;
  try {
    const [phaseDetail, documentList] = await Promise.all([
      phaseStore.fetchPhaseDetail(phaseId),
      listDocuments({
        includeHistory: true,
        phaseId,
        subProjectId: props.subProjectId,
      }),
    ]);
    detail.value = phaseDetail;
    documents.value = documentList.items;
  } finally {
    documentsLoading.value = false;
  }
}

async function handleUploaded(): Promise<void> {
  await loadSelectedPhase();
}

async function handleDownload(documentItem: DocumentRead): Promise<void> {
  const blob = await downloadDocument(documentItem.id);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = documentItem.file_name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function isMissing(document: PhaseRequiredDocumentRead): boolean {
  return missingDocTypes.value.has(document.doc_type);
}
</script>

<template>
  <section class="project-detail-band phase-document-panel">
    <div class="project-detail-band__header">
      <div>
        <h3>环节文档</h3>
        <span>必传完成度 {{ completionText }}</span>
      </div>
    </div>

    <div v-if="phaseOptions.length > 0" class="phase-document-panel__tabs">
      <button
        v-for="phase in phaseOptions"
        :key="phase.id"
        class="phase-document-panel__tab"
        :class="{ 'phase-document-panel__tab--active': selectedPhaseId === phase.id }"
        :data-test="`select-doc-phase-${phase.id}`"
        type="button"
        @click="selectPhase(phase)"
      >
        {{ phase.phase_no }}. {{ phase.name }}
      </button>
    </div>

    <el-skeleton v-if="phaseStore.detailLoading && !detail" animated />

    <template v-else-if="detail">
      <div class="phase-document-panel__required">
        <article
          v-for="document in detail.required_documents"
          :key="document.doc_type"
          class="phase-document-panel__requirement"
          :class="{ 'phase-document-panel__requirement--missing': isMissing(document) }"
          :data-test="
            isMissing(document)
              ? `missing-doc-${document.doc_type}`
              : `required-doc-${document.doc_type}`
          "
        >
          <div class="phase-document-panel__requirement-header">
            <div>
              <h4>{{ document.doc_type }}</h4>
              <p>数量规则 {{ document.qty_rule }}</p>
            </div>
            <el-tag :type="isMissing(document) ? 'danger' : 'success'">
              {{ isMissing(document) ? '缺失' : '已满足' }}
            </el-tag>
          </div>
          <DocumentUploader
            :doc-type="document.doc_type"
            :phase-id="detail.id"
            :sub-project-id="props.subProjectId"
            @uploaded="handleUploaded"
          />
        </article>
      </div>

      <el-empty v-if="detail.required_documents.length === 0" description="当前环节无必传文档" />

      <DocumentList :documents="documents" :loading="documentsLoading" @download="handleDownload" />
    </template>

    <el-empty v-else-if="!phaseStore.loading" description="暂无环节文档" />
  </section>
</template>
