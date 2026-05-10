<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive } from 'vue';

import { MobileReadOnlyNotice } from '@/components/common';
import { useRevokeRequestStore } from '@/stores/useRevokeRequestStore';
import {
  REVOKE_REVIEW_DECISION_LABELS,
  type RevokeRequestRead,
  type RevokeReviewDecision,
} from '@/types/revokeRequests';

const revokeStore = useRevokeRequestStore();
const reviewComments = reactive<Record<string, string>>({});

const reviewRows = computed(() => revokeStore.requests);

onMounted(loadPendingRequests);

async function loadPendingRequests(): Promise<void> {
  await revokeStore.fetchRequests({ status: 'pending' });
  for (const request of revokeStore.requests) {
    reviewComments[request.id] = reviewComments[request.id] ?? '';
  }
}

async function submitReview(
  request: RevokeRequestRead,
  decision: RevokeReviewDecision,
): Promise<void> {
  await revokeStore.reviewRequest(request.id, {
    decision,
    reviewComment: reviewComments[request.id]?.trim() || null,
  });
  ElMessage.success(`撤销申请已${REVOKE_REVIEW_DECISION_LABELS[decision]}`);
  await loadPendingRequests();
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : '-';
}
</script>

<template>
  <section class="admin-page project-page revoke-page">
    <div class="admin-page__header">
      <div>
        <h2>撤销审核</h2>
        <p>处理待审核的环节撤销申请</p>
      </div>
    </div>

    <MobileReadOnlyNotice
      data-test="mobile-read-only-review"
      message="移动端仅支持查看审核信息，请切换到 PC 端处理审核。"
    />

    <section class="project-detail-band">
      <table class="revoke-table">
        <thead>
          <tr>
            <th>子项目</th>
            <th>环节</th>
            <th>申请人</th>
            <th>原因</th>
            <th>提交时间</th>
            <th>审核意见</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="request in reviewRows" :key="request.id" data-test="revoke-review-row">
            <td>{{ request.sub_project_id }}</td>
            <td>{{ request.phase_id }}</td>
            <td>{{ request.requester_id }}</td>
            <td>{{ request.reason }}</td>
            <td>{{ formatDate(request.created_at) }}</td>
            <td>
              <el-input v-model="reviewComments[request.id]" data-test="revoke-review-comment" />
            </td>
            <td class="revoke-table__actions desktop-only-action">
              <el-button
                data-test="approve-revoke-request"
                :loading="revokeStore.reviewingId === request.id"
                size="small"
                type="primary"
                @click="submitReview(request, 'approve')"
              >
                通过
              </el-button>
              <el-button
                data-test="reject-revoke-request"
                :loading="revokeStore.reviewingId === request.id"
                size="small"
                type="danger"
                @click="submitReview(request, 'reject')"
              >
                驳回
              </el-button>
            </td>
          </tr>
        </tbody>
      </table>
      <el-empty
        v-if="!revokeStore.loading && reviewRows.length === 0"
        description="暂无待审核撤销申请"
      />
    </section>
  </section>
</template>

<style scoped>
.revoke-table {
  border-collapse: collapse;
  width: 100%;
}

.revoke-table th,
.revoke-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px;
  text-align: left;
}

.revoke-table__actions {
  display: flex;
  gap: 8px;
}
</style>
