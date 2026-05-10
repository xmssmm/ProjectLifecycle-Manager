<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { ConfirmDialog } from '@/components/common';
import { useMainProjectStore } from '@/stores/useMainProjectStore';
import type {
  MainProjectCreatePayload,
  MainProjectRead,
  MainProjectUpdatePayload,
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

const props = defineProps<{
  projectId?: string;
}>();

const mainProjectStore = useMainProjectStore();
const form = reactive<FormState>({
  dept_id: '',
  expected_finish_date: '',
  name: '',
  remark: '',
  total_budget: '',
});
const errors = reactive<Partial<Record<keyof FormState, string>>>({});
const loading = ref(false);
const saving = ref(false);
const submitConfirmVisible = ref(false);

const isEditMode = computed(() => Boolean(props.projectId));
const pageTitle = computed(() => (isEditMode.value ? '编辑主项目' : '新建主项目'));
const submitText = computed(() => (isEditMode.value ? '保存并重新提交' : '创建并提交审核'));
const budgetNumber = computed<number | undefined>({
  get: () => {
    const budgetValue = String(form.total_budget).trim();
    return budgetValue ? Number(budgetValue) : undefined;
  },
  set: (value) => {
    form.total_budget = value ?? '';
  },
});

onMounted(async () => {
  if (!props.projectId) {
    return;
  }

  loading.value = true;
  try {
    const project = await mainProjectStore.fetchMainProjectDetail(props.projectId);
    hydrateForm(project);
  } finally {
    loading.value = false;
  }
});

function hydrateForm(project: MainProjectRead | null | undefined): void {
  if (!project) {
    return;
  }
  form.name = project.name;
  form.dept_id = project.dept_id;
  form.total_budget = project.total_budget;
  form.expected_finish_date = project.expected_finish_date?.slice(0, 10) ?? '';
  form.remark = project.remark ?? '';
}

function validateForm(): boolean {
  Object.keys(errors).forEach((key) => {
    delete errors[key as keyof FormState];
  });

  if (!form.name.trim()) {
    errors.name = '项目名称必填';
  }
  if (!form.dept_id.trim()) {
    errors.dept_id = '部门必填';
  }
  const budgetValue = String(form.total_budget).trim();
  if (!budgetValue) {
    errors.total_budget = '总预算必填';
  } else if (!Number.isFinite(Number(budgetValue)) || Number(budgetValue) < 0) {
    errors.total_budget = '总预算必须为非负数字';
  }
  if (!form.expected_finish_date) {
    errors.expected_finish_date = '预计完成日期必填';
  }

  return Object.keys(errors).length === 0;
}

function buildPayload(): MainProjectCreatePayload {
  const budgetValue = String(form.total_budget).trim();
  return {
    dept_id: form.dept_id.trim(),
    expected_finish_date: form.expected_finish_date,
    name: form.name.trim(),
    remark: form.remark.trim() || null,
    total_budget: Number(budgetValue).toFixed(2),
  };
}

async function saveProject(): Promise<MainProjectRead | null> {
  if (!validateForm()) {
    return null;
  }

  saving.value = true;
  try {
    const payload = buildPayload();
    if (props.projectId) {
      return await mainProjectStore.updateMainProject(
        props.projectId,
        payload satisfies MainProjectUpdatePayload,
      );
    }
    return await mainProjectStore.createMainProject(payload);
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '保存主项目失败'));
    return null;
  } finally {
    saving.value = false;
  }
}

function openSubmitConfirm(): void {
  if (!validateForm()) {
    return;
  }
  submitConfirmVisible.value = true;
}

async function submitForReview(): Promise<void> {
  const project = await saveProject();
  if (!project) {
    return;
  }

  saving.value = true;
  try {
    await mainProjectStore.submitMainProject(project.id);
    ElMessage.success('主项目已提交审核');
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '提交审核失败'));
  } finally {
    saving.value = false;
  }
}

async function saveOnly(): Promise<void> {
  const project = await saveProject();
  if (project) {
    ElMessage.success(isEditMode.value ? '主项目已更新' : '主项目已创建');
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
        <h2>{{ pageTitle }}</h2>
        <p>填写立项信息，保存后可提交给审核人处理。</p>
      </div>
      <router-link :to="{ name: 'main-projects' }">
        <el-button>返回列表</el-button>
      </router-link>
    </div>

    <el-skeleton v-if="loading" animated />

    <section v-else class="project-form-band">
      <el-form label-width="120px">
        <el-form-item label="项目名称" :error="errors.name">
          <el-input v-model="form.name" data-test="project-name" maxlength="200" />
        </el-form-item>
        <el-form-item label="部门 ID" :error="errors.dept_id">
          <el-input v-model="form.dept_id" data-test="project-dept" />
        </el-form-item>
        <el-form-item label="总预算" :error="errors.total_budget">
          <el-input-number
            v-model="budgetNumber"
            data-test="project-budget"
            :min="0"
            :precision="2"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item label="预计完成" :error="errors.expected_finish_date">
          <el-date-picker
            v-model="form.expected_finish_date"
            data-test="project-finish"
            format="YYYY-MM-DD"
            type="date"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" data-test="project-remark" :rows="4" type="textarea" />
        </el-form-item>

        <div class="project-form-actions">
          <el-button :loading="saving" @click="saveOnly">保存</el-button>
          <el-button
            data-test="submit-for-review"
            :loading="saving"
            type="primary"
            @click="openSubmitConfirm"
          >
            {{ submitText }}
          </el-button>
        </div>
      </el-form>
    </section>

    <ConfirmDialog
      v-model="submitConfirmVisible"
      confirm-text="提交审核"
      message="提交后将通知审核人处理，审核前请确认项目信息无误。"
      title="提交主项目审核"
      @confirm="submitForReview"
    />
  </section>
</template>
