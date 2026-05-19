<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { downloadDocument, listDocuments } from '@/api/documents';
import DocumentList from '@/components/document/DocumentList.vue';
import DocumentUploader from '@/components/document/DocumentUploader.vue';
import { useAcceptanceStepStore } from '@/stores/useAcceptanceStepStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePhaseStore } from '@/stores/usePhaseStore';
import { ACCEPTANCE_STEP_STATUS_LABELS, type AcceptanceStepRead } from '@/types/acceptanceSteps';
import type { DocumentRead } from '@/types/documents';
import type {
  PhaseDetailRead,
  PhaseRead,
  PhaseRequiredDocumentRead,
  ProcurementType,
} from '@/types/phases';
import { documentLabel } from '@/utils/documentLabels';

const props = defineProps<{
  subProjectId: string;
}>();
const emit = defineEmits<{
  promoted: [];
}>();

const authStore = useAuthStore();
const phaseStore = usePhaseStore();
const acceptanceStepStore = useAcceptanceStepStore();
const documents = ref<DocumentRead[]>([]);
const documentsLoading = ref(false);
const detail = ref<PhaseDetailRead | null>(null);
const selectedPhaseId = ref('');
const stepError = ref('');
const stepForm = reactive({
  description: '',
  planDate: '',
  responsibleId: '',
  stepName: '',
  stepNo: 1,
});
const procurementTypeOptions: Array<{ label: string; value: ProcurementType }> = [
  { label: '询价类', value: 'inquiry' },
  { label: '招标类', value: 'bidding' },
  { label: '单一来源', value: 'single_source' },
];

const phaseOptions = computed(() =>
  phaseStore.phases
    .filter((phase) => phase.sub_project_id === props.subProjectId)
    .sort((left, right) => left.phase_no - right.phase_no),
);
const missingDocTypes = computed(() => new Set(detail.value?.completion.missing_doc_types ?? []));
const missingDocLabels = computed(() => [...missingDocTypes.value].map(documentLabel));
const completionText = computed(() => {
  const completion = detail.value?.completion;
  if (!completion) {
    return '0 / 0';
  }
  return `${completion.uploaded_total} / ${completion.required_total}`;
});
const canPromoteSelectedPhase = computed(
  () =>
    Boolean(detail.value) &&
    detail.value?.status === 'in_progress' &&
    missingDocTypes.value.size === 0,
);
const promoteBlockerText = computed(() => {
  if (!detail.value) {
    return '';
  }
  if (detail.value.status !== 'in_progress') {
    return '当前环节不在进行中，暂不能推进';
  }
  if (missingDocTypes.value.size > 0) {
    return `缺少材料：${missingDocLabels.value.join('、')}`;
  }
  return '';
});
const isAcceptancePhase = computed(() => detail.value?.phase_no === 4);
const isCompletedPhase = computed(() => detail.value?.status === 'completed');
const acceptanceSteps = computed(() =>
  detail.value ? (acceptanceStepStore.stepsByPhase[detail.value.id] ?? []) : [],
);

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
    if (phaseDetail.phase_no === 4) {
      await acceptanceStepStore.fetchSteps(phaseId);
    }
  } finally {
    documentsLoading.value = false;
  }
}

async function handleUploaded(): Promise<void> {
  await loadSelectedPhase();
}

async function updateProcurementType(value: ProcurementType): Promise<void> {
  if (!detail.value) {
    return;
  }
  await phaseStore.updateProcurementType(detail.value.id, value);
  await loadSelectedPhase();
}

async function promoteSelectedPhase(): Promise<void> {
  if (!detail.value || !canPromoteSelectedPhase.value) {
    return;
  }
  await phaseStore.promotePhase(detail.value.id);
  detail.value = null;
  documents.value = [];
  await phaseStore.fetchPhases(props.subProjectId);
  selectDefaultPhase();
  emit('promoted');
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

async function submitAcceptanceStep(): Promise<void> {
  if (!detail.value) {
    return;
  }

  stepError.value = '';
  const stepNo = Number(stepForm.stepNo);
  const stepName = stepForm.stepName.trim();
  const responsibleId = stepForm.responsibleId.trim();
  if (!Number.isFinite(stepNo) || stepNo < 1 || !stepName || !responsibleId) {
    stepError.value = '步骤序号、名称、责任人必填';
    return;
  }

  await acceptanceStepStore.createStep(detail.value.id, {
    description: stepForm.description.trim() || null,
    planDate: stepForm.planDate || null,
    responsibleId,
    stepName,
    stepNo,
  });
  resetStepForm(stepNo + 1);
}

async function completeAcceptanceStep(step: AcceptanceStepRead): Promise<void> {
  if (!detail.value || step.status === 'completed') {
    return;
  }
  await acceptanceStepStore.updateStep(detail.value.id, step.id, { status: 'completed' });
  await loadSelectedPhase();
}

function resetStepForm(nextStepNo = 1): void {
  stepForm.description = '';
  stepForm.planDate = '';
  stepForm.responsibleId = '';
  stepForm.stepName = '';
  stepForm.stepNo = nextStepNo;
}

function stepStatusLabel(step: AcceptanceStepRead): string {
  return ACCEPTANCE_STEP_STATUS_LABELS[step.status];
}

function formatOptionalDate(value: string | null): string {
  return value || '-';
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
      <div class="phase-document-panel__promote">
        <el-alert v-if="promoteBlockerText" show-icon :title="promoteBlockerText" type="warning" />
        <el-button
          data-test="promote-selected-phase"
          :disabled="!canPromoteSelectedPhase"
          :loading="phaseStore.promotingId === detail.id"
          type="primary"
          @click="promoteSelectedPhase"
        >
          {{ canPromoteSelectedPhase ? '推进环节' : '暂不能推进' }}
        </el-button>
      </div>

      <el-form v-if="detail.phase_no === 2" class="phase-document-panel__procurement">
        <el-form-item label="采购类型">
          <el-select
            :model-value="detail.procurement_type"
            data-test="procurement-type-select"
            :disabled="detail.status === 'completed'"
            placeholder="请选择采购类型"
            @update:model-value="updateProcurementType"
          >
            <el-option
              v-for="option in procurementTypeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
      </el-form>

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
              <h4>{{ documentLabel(document.doc_type) }}</h4>
              <p>数量规则 {{ document.qty_rule }}</p>
            </div>
            <el-tag :type="isMissing(document) ? 'danger' : 'success'">
              {{ isMissing(document) ? '缺失' : '已满足' }}
            </el-tag>
          </div>
          <DocumentUploader
            v-if="!isCompletedPhase"
            :doc-type="document.doc_type"
            :phase-id="detail.id"
            :sub-project-id="props.subProjectId"
            @uploaded="handleUploaded"
          />
          <p v-else class="phase-document-panel__locked-upload">已完成环节不可继续上传</p>
        </article>
      </div>

      <el-empty v-if="detail.required_documents.length === 0" description="当前环节无必传文档" />

      <section
        v-if="isAcceptancePhase"
        class="phase-document-panel__acceptance"
        data-test="acceptance-step-panel"
      >
        <div class="phase-document-panel__acceptance-header">
          <div>
            <h4>验收步骤</h4>
            <p>按步骤指派责任人、上传验收报告并完成验收。</p>
          </div>
          <el-tag>{{ acceptanceSteps.length }} 项</el-tag>
        </div>

        <form class="phase-document-panel__step-form" @submit.prevent="submitAcceptanceStep">
          <label>
            <span>序号</span>
            <!-- prettier-ignore -->
            <input v-model.number="stepForm.stepNo" data-test="acceptance-step-no" min="1" type="number">
          </label>
          <label>
            <span>步骤名称</span>
            <!-- prettier-ignore -->
            <input v-model="stepForm.stepName" data-test="acceptance-step-name" type="text">
          </label>
          <label>
            <span>责任人</span>
            <!-- prettier-ignore -->
            <input v-model="stepForm.responsibleId" data-test="acceptance-step-responsible" type="text">
          </label>
          <label>
            <span>计划日期</span>
            <!-- prettier-ignore -->
            <input v-model="stepForm.planDate" data-test="acceptance-step-plan-date" type="date">
          </label>
          <label class="phase-document-panel__step-form-description">
            <span>说明</span>
            <textarea
              v-model="stepForm.description"
              data-test="acceptance-step-description"
              rows="2"
            />
          </label>
          <button
            class="phase-document-panel__step-submit"
            data-test="create-acceptance-step"
            type="button"
            @click="submitAcceptanceStep"
          >
            新增步骤
          </button>
        </form>
        <p v-if="stepError" class="phase-document-panel__step-error">{{ stepError }}</p>

        <div v-if="acceptanceSteps.length > 0" class="phase-document-panel__step-list">
          <article
            v-for="step in acceptanceSteps"
            :key="step.id"
            class="phase-document-panel__step-card"
          >
            <div class="phase-document-panel__step-main">
              <div>
                <h5>{{ step.step_no }}. {{ step.step_name }}</h5>
                <p>{{ step.description || '暂无说明' }}</p>
              </div>
              <el-tag :type="step.status === 'completed' ? 'success' : 'warning'">
                {{ stepStatusLabel(step) }}
              </el-tag>
            </div>
            <div class="phase-document-panel__step-meta">
              <span>责任人 {{ step.responsible_id }}</span>
              <span>计划 {{ formatOptionalDate(step.plan_date) }}</span>
              <span>完成 {{ formatOptionalDate(step.completed_at) }}</span>
            </div>
            <div class="phase-document-panel__step-actions">
              <DocumentUploader
                v-if="!isCompletedPhase"
                :acceptance-step-id="step.id"
                doc-type="acceptance_report"
                :phase-id="detail.id"
                :sub-project-id="props.subProjectId"
                @uploaded="handleUploaded"
              />
              <p v-else class="phase-document-panel__locked-upload">已完成环节不可继续上传</p>
              <button
                class="phase-document-panel__step-complete"
                :data-test="`complete-acceptance-step-${step.id}`"
                :disabled="
                  step.status === 'completed' || acceptanceStepStore.updatingId === step.id
                "
                type="button"
                @click="completeAcceptanceStep(step)"
              >
                完成步骤
              </button>
            </div>
          </article>
        </div>
        <el-empty v-else description="暂无验收步骤" />
      </section>

      <DocumentList
        :documents="documents"
        :loading="documentsLoading"
        :timezone="authStore.user?.timezone"
        @download="handleDownload"
      />
    </template>

    <el-empty v-else-if="!phaseStore.loading" description="暂无环节文档" />
  </section>
</template>

<style scoped>
.phase-document-panel__acceptance {
  border: 1px solid #d8dee8;
  border-radius: 8px;
  margin-bottom: 20px;
  padding: 16px;
}

.phase-document-panel__procurement {
  margin-bottom: 16px;
}

.phase-document-panel__promote {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}

.phase-document-panel__acceptance-header,
.phase-document-panel__step-main,
.phase-document-panel__step-actions {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.phase-document-panel__acceptance-header h4,
.phase-document-panel__step-card h5 {
  margin: 0;
}

.phase-document-panel__acceptance-header p,
.phase-document-panel__step-card p {
  color: #64748b;
  margin: 4px 0 0;
}

.phase-document-panel__step-form {
  display: grid;
  gap: 12px;
  grid-template-columns: 96px repeat(3, minmax(140px, 1fr)) auto;
  margin-top: 16px;
}

.phase-document-panel__step-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.phase-document-panel__step-form span,
.phase-document-panel__step-meta {
  color: #64748b;
  font-size: 13px;
}

.phase-document-panel__step-form input,
.phase-document-panel__step-form textarea {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  min-height: 34px;
  padding: 6px 8px;
}

.phase-document-panel__step-form-description {
  grid-column: 1 / -2;
}

.phase-document-panel__step-submit,
.phase-document-panel__step-complete {
  align-self: end;
  background: #1f6feb;
  border: 0;
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  min-height: 36px;
  padding: 0 14px;
}

.phase-document-panel__step-complete {
  background: #16a34a;
}

.phase-document-panel__step-complete:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.phase-document-panel__step-error {
  color: #dc2626;
  margin: 10px 0 0;
}

.phase-document-panel__locked-upload {
  color: #64748b;
  font-size: 13px;
  margin: 0;
}

.phase-document-panel__step-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.phase-document-panel__step-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
}

.phase-document-panel__step-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 12px 0;
}

@media (width <= 900px) {
  .phase-document-panel__step-form {
    grid-template-columns: 1fr;
  }

  .phase-document-panel__step-form-description {
    grid-column: auto;
  }
}
</style>
