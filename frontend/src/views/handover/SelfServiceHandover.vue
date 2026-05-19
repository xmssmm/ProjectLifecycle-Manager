<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref } from 'vue';

import { useAuthStore } from '@/stores/useAuthStore';
import { useHandoverRequestStore } from '@/stores/useHandoverRequestStore';
import { useSubProjectStore } from '@/stores/useSubProjectStore';
import { useUserStore } from '@/stores/useUserStore';
import { HANDOVER_REQUEST_STATUS_LABELS, type HandoverRequestRead } from '@/types/handoverRequests';
import { PROJECT_STATUS_LABELS, type SubProjectRead } from '@/types/projects';

const ACTIVE_HANDOVER_STATUSES = new Set(['not_started', 'in_progress', 'completed']);
const FORCE_AFTER_MS = 7 * 24 * 60 * 60 * 1000;

const authStore = useAuthStore();
const handoverStore = useHandoverRequestStore();
const subProjectStore = useSubProjectStore();
const userStore = useUserStore();

const candidateId = ref('');
const errorMessage = ref('');
const reason = ref('');
const reviewComments = ref<Record<string, string>>({});
const selectedProjectIds = ref<string[]>([]);

const currentUserId = computed(() => authStore.user?.id ?? '');
const currentRole = computed(() => authStore.user?.role);
const canSubmitRequest = computed(() => currentRole.value === 'proj_leader');
const canReviewRequests = computed(
  () => currentRole.value === 'admin' || currentRole.value === 'dept_manager',
);
const activeProjects = computed(() =>
  subProjectStore.subProjects.filter(
    (project) =>
      project.manager_id === currentUserId.value && ACTIVE_HANDOVER_STATUSES.has(project.status),
  ),
);
const candidateOptions = computed(() =>
  userStore.users.filter(
    (user) =>
      user.role === 'proj_leader' && user.status === 'active' && user.id !== currentUserId.value,
  ),
);
const candidateRequests = computed(() =>
  handoverStore.requests.filter(
    (request) =>
      request.status === 'pending_candidate' && request.to_user_id === currentUserId.value,
  ),
);
const reviewRequests = computed(() => {
  if (!canReviewRequests.value) {
    return [];
  }
  return handoverStore.requests.filter((request) => request.status === 'pending_review');
});
const forceableRequests = computed(() =>
  handoverStore.requests.filter(
    (request) =>
      currentRole.value === 'admin' &&
      request.status === 'pending_candidate' &&
      Date.now() - new Date(request.created_at).getTime() >= FORCE_AFTER_MS,
  ),
);

onMounted(loadPage);

async function loadPage(): Promise<void> {
  await Promise.all([
    handoverStore.fetchRequests({}),
    subProjectStore.fetchSubProjects({ page: 1, pageSize: 100 }),
    userStore.fetchUsers({ page: 1, pageSize: 100, role: 'proj_leader' }),
  ]);
}

async function submitRequest(): Promise<void> {
  errorMessage.value = validateSubmit();
  if (errorMessage.value) {
    return;
  }
  await handoverStore.submitRequest({
    reason: reason.value.trim(),
    subProjectIds: selectedProjectIds.value,
    toUserId: candidateId.value,
  });
  ElMessage.success('转交申请已提交');
  selectedProjectIds.value = [];
  candidateId.value = '';
  reason.value = '';
  await handoverStore.fetchRequests({});
}

async function candidateReview(request: HandoverRequestRead, decision: 'confirm' | 'reject') {
  await handoverStore.candidateReview(request.id, { decision });
  ElMessage.success(decision === 'confirm' ? '已确认接收' : '已拒绝接收');
  await handoverStore.fetchRequests({});
}

async function reviewRequest(request: HandoverRequestRead, decision: 'approve' | 'reject') {
  await handoverStore.reviewRequest(request.id, {
    decision,
    reviewComment: reviewComments.value[request.id]?.trim() || null,
  });
  ElMessage.success(decision === 'approve' ? '转交已通过' : '转交已驳回');
  await handoverStore.fetchRequests({});
}

async function forceRequest(request: HandoverRequestRead) {
  await handoverStore.forceRequest(request.id);
  ElMessage.success('已强制转交');
  await handoverStore.fetchRequests({});
}

function validateSubmit(): string {
  if (!selectedProjectIds.value.length) {
    return '请选择需要转交的子项目';
  }
  if (!candidateId.value) {
    return '请选择候选负责人';
  }
  if (!reason.value.trim()) {
    return '请填写转交原因';
  }
  return '';
}

function toggleProject(projectId: string, checked: boolean): void {
  selectedProjectIds.value = checked
    ? [...selectedProjectIds.value, projectId]
    : selectedProjectIds.value.filter((id) => id !== projectId);
}

function projectLabel(projectId: string): string {
  const project = subProjectStore.subProjects.find((item) => item.id === projectId);
  return project ? `${project.project_no} ${project.name}` : projectId;
}

function statusLabel(request: HandoverRequestRead): string {
  return HANDOVER_REQUEST_STATUS_LABELS[request.status];
}

function statusTagType(request: HandoverRequestRead): 'danger' | 'success' | 'warning' {
  if (request.status === 'approved' || request.status === 'forced') {
    return 'success';
  }
  if (request.status === 'candidate_rejected' || request.status === 'review_rejected') {
    return 'danger';
  }
  return 'warning';
}

function formatProjectStatus(project: SubProjectRead): string {
  return PROJECT_STATUS_LABELS[project.status];
}
</script>

<template>
  <section class="admin-page project-page handover-self-page">
    <div class="admin-page__header">
      <div>
        <h2>自助转交</h2>
        <p>发起负责人转交、确认接收和处理审核</p>
      </div>
    </div>

    <section v-if="canSubmitRequest" class="project-form-band handover-self-panel">
      <div class="project-detail-band__header">
        <h3>发起转交</h3>
        <span>{{ activeProjects.length }} 个可转交子项目</span>
      </div>
      <el-form label-width="112px">
        <el-form-item label="候选负责人">
          <el-select v-model="candidateId" data-test="self-to-user" filterable>
            <el-option
              v-for="user in candidateOptions"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="转交原因">
          <el-input v-model="reason" data-test="self-handover-reason" />
        </el-form-item>
      </el-form>
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
      <table class="handover-self-table">
        <thead>
          <tr>
            <th>选择</th>
            <th>子项目</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="project in activeProjects" :key="project.id">
            <td>
              <el-checkbox
                data-test="handover-project"
                :model-value="selectedProjectIds.includes(project.id)"
                @update:model-value="toggleProject(project.id, Boolean($event))"
              />
            </td>
            <td>{{ project.project_no }} {{ project.name }}</td>
            <td>{{ formatProjectStatus(project) }}</td>
          </tr>
        </tbody>
      </table>
      <el-empty v-if="!activeProjects.length" description="暂无可转交子项目" />
      <div class="project-form-actions">
        <el-button
          data-test="submit-self-handover"
          :loading="handoverStore.submitting"
          type="primary"
          @click="submitRequest"
        >
          提交申请
        </el-button>
      </div>
    </section>

    <section class="project-detail-band">
      <div class="project-detail-band__header">
        <h3>待我确认</h3>
        <span>{{ candidateRequests.length }} 项</span>
      </div>
      <div class="handover-card-list">
        <article v-for="request in candidateRequests" :key="request.id" class="handover-card">
          <p>{{ request.reason }}</p>
          <small>{{ request.sub_project_ids.map(projectLabel).join('、') }}</small>
          <div class="handover-card__actions">
            <el-button
              data-test="confirm-candidate"
              size="small"
              @click="candidateReview(request, 'confirm')"
            >
              确认接收
            </el-button>
            <el-button size="small" type="danger" @click="candidateReview(request, 'reject')">
              拒绝
            </el-button>
          </div>
        </article>
      </div>
      <el-empty v-if="!candidateRequests.length" description="暂无待确认申请" />
    </section>

    <section class="project-detail-band">
      <div class="project-detail-band__header">
        <h3>待审核</h3>
        <span>{{ reviewRequests.length }} 项</span>
      </div>
      <div class="handover-card-list">
        <article v-for="request in reviewRequests" :key="request.id" class="handover-card">
          <p>{{ request.reason }}</p>
          <small>{{ request.sub_project_ids.map(projectLabel).join('、') }}</small>
          <el-input v-model="reviewComments[request.id]" placeholder="审核意见" />
          <div class="handover-card__actions">
            <el-button
              data-test="approve-handover-request"
              size="small"
              type="primary"
              @click="reviewRequest(request, 'approve')"
            >
              通过
            </el-button>
            <el-button size="small" type="danger" @click="reviewRequest(request, 'reject')">
              驳回
            </el-button>
          </div>
        </article>
      </div>
      <el-empty v-if="!reviewRequests.length" description="暂无待审核申请" />
    </section>

    <section class="project-detail-band">
      <div class="project-detail-band__header">
        <h3>申请记录</h3>
        <span>{{ handoverStore.total }} 项</span>
      </div>
      <table class="handover-self-table">
        <thead>
          <tr>
            <th>转交项目</th>
            <th>候选人</th>
            <th>状态</th>
            <th>原因</th>
            <th>兜底</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="request in handoverStore.requests" :key="request.id">
            <td>{{ request.sub_project_ids.map(projectLabel).join('、') }}</td>
            <td>{{ request.to_user_id }}</td>
            <td>
              <el-tag :type="statusTagType(request)">{{ statusLabel(request) }}</el-tag>
            </td>
            <td>{{ request.reason }}</td>
            <td>
              <el-button
                v-if="forceableRequests.some((item) => item.id === request.id)"
                :data-test="`force-handover-request-${request.id}`"
                size="small"
                type="warning"
                @click="forceRequest(request)"
              >
                强制转交
              </el-button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>

<style scoped>
.handover-self-panel {
  margin-bottom: 20px;
}

.handover-self-table {
  border-collapse: collapse;
  width: 100%;
}

.handover-self-table th,
.handover-self-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px;
  text-align: left;
}

.handover-card-list {
  display: grid;
  gap: 12px;
}

.handover-card {
  border: 1px solid #d8dee8;
  border-radius: 8px;
  padding: 14px;
}

.handover-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
</style>
