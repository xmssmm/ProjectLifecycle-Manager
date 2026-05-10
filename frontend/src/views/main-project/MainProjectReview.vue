<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { StatusTag } from '@/components/common';
import { usePermission } from '@/composables/usePermission';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMainProjectStore } from '@/stores/useMainProjectStore';
import type {
  MainProjectRead,
  MainProjectUpdatePayload,
  ProjectReviewDecision,
} from '@/types/projects';

interface ApiErrorResponse {
  message?: string;
}

interface FormState {
  dept_id: string;
  expected_finish_date: string;
  name: string;
  remark: string;
  total_budget: number | string;
}

interface DiffRow {
  after: string;
  before: string;
  field: keyof MainProjectUpdatePayload;
  label: string;
}

const props = defineProps<{
  projectId: string;
}>();

const mainProjectStore = useMainProjectStore();
const authStore = useAuthStore();
const { can } = usePermission();

const loading = ref(false);
const submitting = ref(false);
const reviewComment = ref('');
const originalForm = ref<FormState | null>(null);
const form = reactive<FormState>({
  dept_id: '',
  expected_finish_date: '',
  name: '',
  remark: '',
  total_budget: '',
});

const project = computed(() => mainProjectStore.currentProject);
const selfReviewBlocked = computed(
  () => project.value?.creator_id === authStore.user?.id && authStore.user?.role !== 'admin',
);
const canSubmitReview = computed(
  () =>
    project.value?.status === 'pending_review' &&
    can('main_project.review') &&
    !selfReviewBlocked.value,
);
const budgetNumber = computed<number | undefined>({
  get: () => {
    const budgetValue = String(form.total_budget).trim();
    return budgetValue ? Number(budgetValue) : undefined;
  },
  set: (value) => {
    form.total_budget = value ?? '';
  },
});

const diffRows = computed<DiffRow[]>(() => {
  if (!originalForm.value) {
    return [];
  }

  const current = normalizeForm(form);
  const original = normalizeForm(originalForm.value);
  return diffFields.flatMap(({ field, label }) =>
    current[field] === original[field]
      ? []
      : [
          {
            after: String(current[field] ?? ''),
            before: String(original[field] ?? ''),
            field,
            label,
          },
        ],
  );
});

const diffFields: Array<{ field: keyof MainProjectUpdatePayload; label: string }> = [
  { field: 'name', label: '项目名称' },
  { field: 'dept_id', label: '部门 ID' },
  { field: 'total_budget', label: '总预算' },
  { field: 'expected_finish_date', label: '预计完成' },
  { field: 'remark', label: '备注' },
];

onMounted(async () => {
  loading.value = true;
  try {
    const loadedProject = await mainProjectStore.fetchMainProjectDetail(props.projectId);
    hydrateForm(loadedProject);
  } finally {
    loading.value = false;
  }
});

function hydrateForm(loadedProject: MainProjectRead | null | undefined): void {
  if (!loadedProject) {
    return;
  }
  form.name = loadedProject.name;
  form.dept_id = loadedProject.dept_id;
  form.total_budget = normalizeBudget(loadedProject.total_budget);
  form.expected_finish_date = loadedProject.expected_finish_date?.slice(0, 10) ?? '';
  form.remark = loadedProject.remark ?? '';
  originalForm.value = { ...form };
}

function normalizeForm(value: FormState): Required<MainProjectUpdatePayload> {
  return {
    dept_id: value.dept_id.trim(),
    expected_finish_date: value.expected_finish_date,
    name: value.name.trim(),
    remark: value.remark.trim() || null,
    total_budget: normalizeBudget(value.total_budget),
  };
}

function normalizeBudget(value: number | string): string {
  const budget = Number(String(value).trim() || 0);
  return Number.isFinite(budget) ? budget.toFixed(2) : '0.00';
}

function buildUpdates(): MainProjectUpdatePayload | null {
  if (!diffRows.value.length) {
    return null;
  }

  const current = normalizeForm(form);
  return Object.fromEntries(diffRows.value.map((row) => [row.field, current[row.field]]));
}

async function submitReview(decision: ProjectReviewDecision): Promise<void> {
  if (!canSubmitReview.value) {
    return;
  }

  submitting.value = true;
  try {
    await mainProjectStore.reviewMainProject(props.projectId, {
      decision,
      review_comment: reviewComment.value.trim() || null,
      updates: buildUpdates(),
    });
    ElMessage.success(decision === 'approve' ? '主项目审核通过' : '主项目已退回');
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '审核主项目失败'));
  } finally {
    submitting.value = false;
  }
}

function readErrorMessage(error: unknown, fallback: string): string {
  const response = (error as { response?: { data?: ApiErrorResponse } }).response?.data;
  return response?.message ?? fallback;
}
</script>

<template>
  <section class="admin-page project-page">
    <div class="admin-page__header">
      <div>
        <h2>主项目审核</h2>
        <p>{{ project?.project_no ?? '加载中' }}</p>
      </div>
      <router-link :to="{ name: 'main-project-detail', params: { id: projectId } }">
        <el-button>返回详情</el-button>
      </router-link>
    </div>

    <el-skeleton v-if="loading" animated />

    <template v-else-if="project">
      <section class="project-detail-band">
        <div class="project-detail-band__header">
          <h3>{{ project.name }}</h3>
          <StatusTag :status="project.status" />
        </div>
        <el-alert
          v-if="selfReviewBlocked"
          title="不能审核自己创建的主项目"
          type="warning"
          show-icon
        />
        <el-alert
          v-else-if="project.status !== 'pending_review'"
          title="当前状态无需审核"
          type="info"
          show-icon
        />
      </section>

      <section class="project-form-band">
        <el-form label-width="120px">
          <el-form-item label="项目名称">
            <el-input v-model="form.name" data-test="review-name" maxlength="200" />
          </el-form-item>
          <el-form-item label="部门 ID">
            <el-input v-model="form.dept_id" data-test="review-dept" />
          </el-form-item>
          <el-form-item label="总预算">
            <el-input-number
              v-model="budgetNumber"
              data-test="review-budget"
              :min="0"
              :precision="2"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="预计完成">
            <el-date-picker
              v-model="form.expected_finish_date"
              data-test="review-finish"
              format="YYYY-MM-DD"
              type="date"
              value-format="YYYY-MM-DD"
            />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" data-test="review-remark" :rows="4" type="textarea" />
          </el-form-item>
          <el-form-item label="审核意见">
            <el-input
              v-model="reviewComment"
              data-test="review-comment"
              :rows="3"
              type="textarea"
            />
          </el-form-item>
        </el-form>
      </section>

      <section class="project-detail-band">
        <h3>修改字段</h3>
        <el-empty v-if="!diffRows.length" description="未修改项目字段" />
        <ul v-else class="project-diff-list">
          <li v-for="row in diffRows" :key="row.field">
            <strong>{{ row.label }}</strong>
            <span>{{ row.before || '-' }}</span>
            <span>→</span>
            <span>{{ row.after || '-' }}</span>
          </li>
        </ul>
      </section>

      <div v-if="canSubmitReview" class="project-form-actions">
        <el-button
          data-test="reject-review"
          :loading="submitting"
          type="danger"
          @click="submitReview('reject')"
        >
          退回
        </el-button>
        <el-button
          data-test="approve-review"
          :loading="submitting"
          type="primary"
          @click="submitReview('approve')"
        >
          通过
        </el-button>
      </div>
    </template>

    <el-empty v-else description="项目不存在" />
  </section>
</template>
