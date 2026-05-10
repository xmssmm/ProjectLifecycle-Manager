<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import { ConfirmDialog, MobileReadOnlyNotice, StatusTag } from '@/components/common';
import { usePermission } from '@/composables/usePermission';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSubProjectStore } from '@/stores/useSubProjectStore';
import type { ProjectReviewDecision, SubProjectReviewPayload } from '@/types/projects';

interface ApiErrorResponse {
  code?: number;
  data?: {
    over_budget_amount?: string;
  };
  message?: string;
}

const props = defineProps<{
  subProjectId: string;
}>();

const authStore = useAuthStore();
const subProjectStore = useSubProjectStore();
const { can } = usePermission();
const loading = ref(false);
const submitting = ref(false);
const reviewComment = ref('');
const overBudgetDialogVisible = ref(false);
const overBudgetReason = ref('');
const overBudgetReasonInput = ref<HTMLTextAreaElement | null>(null);
const overBudgetAmount = ref('');

const subProject = computed(() => subProjectStore.currentSubProject);
const selfReviewBlocked = computed(() => subProject.value?.creator_id === authStore.user?.id);
const canSubmitReview = computed(
  () =>
    subProject.value?.status === 'pending_review' &&
    can('sub_project.review') &&
    !selfReviewBlocked.value,
);

onMounted(async () => {
  loading.value = true;
  try {
    await subProjectStore.fetchSubProjectDetail(props.subProjectId);
  } finally {
    loading.value = false;
  }
});

async function submitReview(
  decision: ProjectReviewDecision,
  overBudget: { confirm: boolean; reason: string | null } = { confirm: false, reason: null },
): Promise<void> {
  if (!canSubmitReview.value) {
    return;
  }

  submitting.value = true;
  try {
    await subProjectStore.reviewSubProject(props.subProjectId, buildPayload(decision, overBudget));
    ElMessage.success(decision === 'approve' ? '子项目审核通过' : '子项目已退回');
  } catch (error) {
    const response = (error as { response?: { data?: ApiErrorResponse } }).response?.data;
    if (response?.code === 3001) {
      overBudgetAmount.value = response.data?.over_budget_amount ?? '';
      overBudgetDialogVisible.value = true;
      return;
    }
    ElMessage.error(response?.message ?? '审核子项目失败');
  } finally {
    submitting.value = false;
  }
}

async function confirmOverBudget(): Promise<void> {
  const reason = (overBudgetReasonInput.value?.value ?? overBudgetReason.value).trim();
  if (!reason) {
    return;
  }
  submitting.value = true;
  try {
    await subProjectStore.reviewSubProject(
      props.subProjectId,
      buildPayload('approve', { confirm: true, reason }),
    );
    ElMessage.success('子项目审核通过');
    overBudgetDialogVisible.value = false;
  } catch (error) {
    const response = (error as { response?: { data?: ApiErrorResponse } }).response?.data;
    ElMessage.error(response?.message ?? '审核子项目失败');
  } finally {
    submitting.value = false;
  }
}

function buildPayload(
  decision: ProjectReviewDecision,
  overBudget: { confirm: boolean; reason: string | null },
): SubProjectReviewPayload {
  return {
    confirm_over_budget: overBudget.confirm,
    decision,
    over_budget_reason: overBudget.reason,
    review_comment: reviewComment.value.trim() || null,
    updates: null,
  };
}

function formatMoney(value: unknown): string {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount)
    ? amount.toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
    : '-';
}
</script>

<template>
  <section class="admin-page project-page">
    <div class="admin-page__header">
      <div>
        <h2>子项目审核</h2>
        <p>{{ subProject?.project_no ?? '加载中' }}</p>
      </div>
      <router-link :to="{ name: 'sub-project-detail', params: { id: subProjectId } }">
        <el-button>返回详情</el-button>
      </router-link>
    </div>

    <el-skeleton v-if="loading" animated />

    <template v-else-if="subProject">
      <MobileReadOnlyNotice
        data-test="mobile-read-only-review"
        message="移动端仅支持查看审核信息，请切换到 PC 端处理审核。"
      />

      <section class="project-detail-band">
        <div class="project-detail-band__header">
          <h3>{{ subProject.name }}</h3>
          <StatusTag :status="subProject.status" />
        </div>
        <p>预算：{{ formatMoney(subProject.budget) }}</p>
        <el-alert
          v-if="selfReviewBlocked"
          title="不能审核自己创建的子项目"
          type="warning"
          show-icon
        />
        <el-alert
          v-else-if="subProject.status !== 'pending_review'"
          title="当前状态无需审核"
          type="info"
          show-icon
        />
      </section>

      <section class="project-form-band">
        <el-form label-width="120px">
          <el-form-item label="审核意见">
            <el-input
              v-model="reviewComment"
              data-test="sub-review-comment"
              :rows="3"
              type="textarea"
            />
          </el-form-item>
        </el-form>
      </section>

      <div v-if="canSubmitReview" class="project-form-actions desktop-only-action">
        <el-button
          data-test="reject-sub-project"
          :loading="submitting"
          type="danger"
          @click="submitReview('reject')"
        >
          退回
        </el-button>
        <el-button
          data-test="approve-sub-project"
          :loading="submitting"
          type="primary"
          @click="submitReview('approve')"
        >
          通过
        </el-button>
      </div>
    </template>

    <el-empty v-else description="子项目不存在" />

    <ConfirmDialog
      v-model="overBudgetDialogVisible"
      confirm-text="继续审核"
      :message="`超预算 ${overBudgetAmount || ''}，请填写确认原因后继续。`"
      title="超预算二次确认"
      type="warning"
      @confirm="confirmOverBudget"
    >
      <textarea
        ref="overBudgetReasonInput"
        v-model="overBudgetReason"
        class="el-input__inner"
        data-test="over-budget-reason"
      />
      <div class="project-form-actions">
        <button
          class="el-button el-button--primary"
          data-test="confirm-over-budget"
          type="button"
          @click="confirmOverBudget"
        >
          继续审核
        </button>
      </div>
    </ConfirmDialog>
  </section>
</template>
