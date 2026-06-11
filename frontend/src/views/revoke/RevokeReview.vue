<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { MobileReadOnlyNotice } from '@/components/common';
import { useRevokeRequestStore } from '@/stores/useRevokeRequestStore';
import {
  REVOKE_REQUEST_STATUS_LABELS,
  REVOKE_REVIEW_DECISION_LABELS,
  type RevokeRequestRead,
  type RevokeRequestStatus,
  type RevokeReviewDecision,
} from '@/types/revokeRequests';

const revokeStore = useRevokeRequestStore();
const reviewComments = reactive<Record<string, string>>({});
const statusFilter = ref<RevokeRequestStatus | ''>('pending');

const reviewRows = computed(() => revokeStore.requests);

onMounted(loadRequests);

async function loadRequests(): Promise<void> {
  await revokeStore.fetchRequests(statusFilter.value ? { status: statusFilter.value } : {});
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
  ElMessage.success(`回退申请已${REVOKE_REVIEW_DECISION_LABELS[decision]}`);
  await loadRequests();
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : '-';
}

function statusLabel(status: RevokeRequestStatus): string {
  return REVOKE_REQUEST_STATUS_LABELS[status];
}
</script>

<template>
  <section class="admin-page project-page revoke-page">
    <div class="admin-page__header">
      <div>
        <h2>回退审核与查询</h2>
        <p>查询全部环节回退情况并处理待审核申请</p>
      </div>
    </div>

    <MobileReadOnlyNotice
      data-test="mobile-read-only-review"
      message="移动端仅支持查看回退信息，请切换到 PC 端处理审核。"
    />

    <section class="project-detail-band">
      <div class="revoke-filter">
        <label>
          <span>状态</span>
          <select v-model="statusFilter" data-test="revoke-status-filter">
            <option value="">全部</option>
            <option value="pending">待审核</option>
            <option value="approved">已通过</option>
            <option value="rejected">已驳回</option>
          </select>
        </label>
        <el-button data-test="search-revoke-requests" @click="loadRequests">查询</el-button>
      </div>
      <table class="revoke-table">
        <thead>
          <tr>
            <th>子项目</th>
            <th>环节</th>
            <th>申请人</th>
            <th>原因</th>
            <th>文件处理</th>
            <th>状态</th>
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
            <td>{{ request.keep_documents ? '保留原文件' : '删除原文件' }}</td>
            <td>{{ statusLabel(request.status) }}</td>
            <td>{{ formatDate(request.created_at) }}</td>
            <td>
              <el-input v-model="reviewComments[request.id]" data-test="revoke-review-comment" />
            </td>
            <td class="revoke-table__actions desktop-only-action">
              <el-button
                v-if="request.status === 'pending'"
                data-test="approve-revoke-request"
                :loading="revokeStore.reviewingId === request.id"
                size="small"
                type="primary"
                @click="submitReview(request, 'approve')"
              >
                通过
              </el-button>
              <el-button
                v-if="request.status === 'pending'"
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
        description="暂无回退申请"
      />
    </section>
  </section>
</template>

<style scoped>
.revoke-table {
  border-collapse: collapse;
  width: 100%;
}

.revoke-filter {
  align-items: end;
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.revoke-filter label {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.revoke-filter select {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  min-height: 34px;
  padding: 6px 8px;
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
