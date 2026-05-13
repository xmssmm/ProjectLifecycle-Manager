<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { ConfirmDialog } from '@/components/common';
import DepartmentSelect from '@/components/form/DepartmentSelect.vue';
import MainProjectSelect from '@/components/form/MainProjectSelect.vue';
import { useSubProjectStore } from '@/stores/useSubProjectStore';
import type {
  SubProjectCreatePayload,
  SubProjectRead,
  SubProjectUpdatePayload,
} from '@/types/projects';

interface ApiErrorResponse {
  message?: string;
}

interface FormState {
  budget: number | string;
  dept_id: string;
  main_project_id: string;
  name: string;
  plan_end_date: string;
  remark: string;
}

const props = defineProps<{
  subProjectId?: string;
}>();

const subProjectStore = useSubProjectStore();
const form = reactive<FormState>({
  budget: '',
  dept_id: '',
  main_project_id: '',
  name: '',
  plan_end_date: '',
  remark: '',
});
const errors = reactive<Partial<Record<keyof FormState, string>>>({});
const loading = ref(false);
const saving = ref(false);
const submitConfirmVisible = ref(false);

const isEditMode = computed(() => Boolean(props.subProjectId));
const pageTitle = computed(() => (isEditMode.value ? '编辑子项目' : '新建子项目'));
const submitText = computed(() => (isEditMode.value ? '保存并重新提交' : '创建并提交审核'));
const budgetNumber = computed<number | undefined>({
  get: () => {
    const budgetValue = String(form.budget).trim();
    return budgetValue ? Number(budgetValue) : undefined;
  },
  set: (value) => {
    form.budget = value ?? '';
  },
});

onMounted(async () => {
  if (!props.subProjectId) {
    return;
  }

  loading.value = true;
  try {
    const subProject = await subProjectStore.fetchSubProjectDetail(props.subProjectId);
    hydrateForm(subProject);
  } finally {
    loading.value = false;
  }
});

function hydrateForm(subProject: SubProjectRead | null | undefined): void {
  if (!subProject) {
    return;
  }
  form.name = subProject.name;
  form.main_project_id = subProject.main_project_id;
  form.dept_id = subProject.dept_id;
  form.budget = subProject.budget;
  form.plan_end_date = subProject.plan_end_date?.slice(0, 10) ?? '';
  form.remark = subProject.remark ?? '';
}

function validateForm(): boolean {
  Object.keys(errors).forEach((key) => {
    delete errors[key as keyof FormState];
  });

  const budgetValue = String(form.budget).trim();
  if (!form.name.trim()) {
    errors.name = '子项目名称必填';
  }
  if (!form.main_project_id.trim()) {
    errors.main_project_id = '主项目必填';
  }
  if (!form.dept_id.trim()) {
    errors.dept_id = '部门必填';
  }
  if (!budgetValue) {
    errors.budget = '预算必填';
  } else if (!Number.isFinite(Number(budgetValue)) || Number(budgetValue) < 0) {
    errors.budget = '预算必须为非负数字';
  }

  return Object.keys(errors).length === 0;
}

function buildCreatePayload(): SubProjectCreatePayload {
  return {
    budget: normalizeBudget(form.budget),
    dept_id: form.dept_id.trim(),
    main_project_id: form.main_project_id.trim(),
    name: form.name.trim(),
    plan_end_date: form.plan_end_date || null,
    remark: form.remark.trim() || null,
  };
}

function buildUpdatePayload(): SubProjectUpdatePayload {
  const payload = buildCreatePayload();
  return {
    budget: payload.budget,
    dept_id: payload.dept_id,
    name: payload.name,
    plan_end_date: payload.plan_end_date,
    remark: payload.remark,
  };
}

function normalizeBudget(value: number | string): string {
  return Number(String(value).trim()).toFixed(2);
}

async function saveSubProject(): Promise<SubProjectRead | null> {
  if (!validateForm()) {
    return null;
  }

  saving.value = true;
  try {
    if (props.subProjectId) {
      return await subProjectStore.updateSubProject(props.subProjectId, buildUpdatePayload());
    }
    return await subProjectStore.createSubProject(buildCreatePayload());
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '保存子项目失败'));
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
  const subProject = await saveSubProject();
  if (!subProject) {
    return;
  }

  saving.value = true;
  try {
    await subProjectStore.submitSubProject(subProject.id);
    ElMessage.success('子项目已提交审核');
  } catch (error) {
    ElMessage.error(readErrorMessage(error, '提交审核失败'));
  } finally {
    saving.value = false;
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
        <p>填写子项目立项信息，提交后进入综合部审核。</p>
      </div>
      <router-link :to="{ name: 'sub-projects' }">
        <el-button>返回列表</el-button>
      </router-link>
    </div>

    <el-skeleton v-if="loading" animated />

    <section v-else class="project-form-band">
      <el-alert
        show-icon
        title="子项目审核通过后会自动生成立项、采购、合同、验收、财务付款、后评价 6 个环节。预算会纳入所选主项目额度校验。"
        type="info"
      />

      <el-form label-width="120px">
        <el-form-item label="子项目名称" :error="errors.name">
          <el-input v-model="form.name" data-test="sub-name" maxlength="200" />
        </el-form-item>
        <el-form-item label="关联主项目" :error="errors.main_project_id">
          <MainProjectSelect
            v-model="form.main_project_id"
            data-test="sub-main-project"
            :disabled="isEditMode"
          />
        </el-form-item>
        <el-form-item label="责任部门" :error="errors.dept_id">
          <DepartmentSelect v-model="form.dept_id" data-test="sub-dept" />
        </el-form-item>
        <el-form-item label="预算" :error="errors.budget">
          <el-input-number
            v-model="budgetNumber"
            data-test="sub-budget"
            :min="0"
            :precision="2"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item label="计划完成">
          <el-date-picker
            v-model="form.plan_end_date"
            data-test="sub-plan-end"
            format="YYYY-MM-DD"
            type="date"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" data-test="sub-remark" :rows="4" type="textarea" />
        </el-form-item>

        <div class="project-form-actions">
          <el-button
            data-test="submit-sub-project"
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
      message="提交后将通知审核人处理，请确认子项目信息无误。"
      title="提交子项目审核"
      @confirm="submitForReview"
    />
  </section>
</template>
