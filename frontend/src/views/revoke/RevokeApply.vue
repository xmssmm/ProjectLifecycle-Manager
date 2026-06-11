<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { usePhaseStore } from '@/stores/usePhaseStore';
import { useRevokeRequestStore } from '@/stores/useRevokeRequestStore';
import { REVOKE_REQUEST_STATUS_LABELS, type RevokeRequestRead } from '@/types/revokeRequests';

const props = defineProps<{
  subProjectId?: string;
}>();

const phaseStore = usePhaseStore();
const revokeStore = useRevokeRequestStore();
const errorMessage = ref('');
const keepDocuments = ref(true);
const reason = ref('');
const selectedPhaseId = ref('');

const completedPhases = computed(() =>
  phaseStore.phases.filter(
    (phase) => phase.sub_project_id === props.subProjectId && phase.status === 'completed',
  ),
);

onMounted(loadPage);

watch(
  () => props.subProjectId,
  async () => {
    selectedPhaseId.value = '';
    await loadPage();
  },
);

async function loadPage(): Promise<void> {
  await Promise.all([
    revokeStore.fetchRequests({}),
    props.subProjectId ? phaseStore.fetchPhases(props.subProjectId) : Promise.resolve(),
  ]);
  selectDefaultPhase();
}

async function submitRequest(): Promise<void> {
  errorMessage.value = '';
  if (!selectedPhaseId.value || !reason.value.trim()) {
    errorMessage.value = '请选择环节并填写回退原因';
    return;
  }
  if (!keepDocuments.value) {
    try {
      await ElMessageBox.confirm(
        '删除将删除该环节原始文件且无法恢复，请谨慎选择。',
        '确认删除原始文件',
        {
          cancelButtonText: '取消',
          confirmButtonText: '删除并提交',
          type: 'warning',
        },
      );
    } catch {
      return;
    }
  }
  await revokeStore.submitRequest({
    keepDocuments: keepDocuments.value,
    phaseId: selectedPhaseId.value,
    reason: reason.value.trim(),
  });
  reason.value = '';
  keepDocuments.value = true;
  ElMessage.success('回退申请已提交');
  await revokeStore.fetchRequests({});
}

function selectDefaultPhase(): void {
  if (!selectedPhaseId.value && completedPhases.value.length > 0) {
    selectedPhaseId.value = completedPhases.value[0].id;
  }
}

function statusLabel(request: RevokeRequestRead): string {
  return REVOKE_REQUEST_STATUS_LABELS[request.status];
}

function statusTagType(request: RevokeRequestRead): 'danger' | 'success' | 'warning' {
  if (request.status === 'approved') {
    return 'success';
  }
  if (request.status === 'rejected') {
    return 'danger';
  }
  return 'warning';
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : '-';
}
</script>

<template>
  <section class="admin-page project-page revoke-page">
    <div class="admin-page__header">
      <div>
        <h2>环节回退申请</h2>
        <p>{{ props.subProjectId ?? '我的回退申请' }}</p>
      </div>
      <router-link
        v-if="props.subProjectId"
        :to="{ name: 'sub-project-detail', params: { id: props.subProjectId } }"
      >
        <el-button>返回子项目</el-button>
      </router-link>
    </div>

    <section v-if="props.subProjectId" class="project-detail-band revoke-apply-band">
      <div class="project-detail-band__header">
        <h3>发起回退</h3>
        <span>{{ completedPhases.length }} 个可回退环节</span>
      </div>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="已完成环节">
          <el-select v-model="selectedPhaseId" data-test="revoke-phase-select">
            <el-option
              v-for="phase in completedPhases"
              :key="phase.id"
              :label="`${phase.phase_no}. ${phase.name}`"
              :value="phase.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="回退原因">
          <el-input v-model="reason" data-test="revoke-reason" />
        </el-form-item>
        <label class="revoke-keep-documents">
          <input
            v-model="keepDocuments"
            data-test="revoke-keep-documents"
            type="checkbox"
          >
          <span>保留原本上传文件</span>
        </label>
        <el-alert
          v-if="!keepDocuments"
          :closable="false"
          title="选择不保留时，审核通过后将删除该环节原始文件且无法恢复。"
          type="warning"
        />
        <el-alert v-if="errorMessage" :closable="false" :title="errorMessage" type="error" />
        <el-button
          data-test="submit-revoke-request"
          :disabled="completedPhases.length === 0"
          :loading="revokeStore.submitting"
          type="primary"
          @click="submitRequest"
        >
          提交申请
        </el-button>
      </el-form>
    </section>

    <section class="project-detail-band">
      <div class="project-detail-band__header">
        <h3>我的回退申请</h3>
        <span>{{ revokeStore.total }} 项</span>
      </div>
      <table class="revoke-table">
        <thead>
          <tr>
            <th>子项目</th>
            <th>环节</th>
            <th>原因</th>
            <th>状态</th>
            <th>审核意见</th>
            <th>提交时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="request in revokeStore.requests" :key="request.id">
            <td>{{ request.sub_project_id }}</td>
            <td>{{ request.phase_id }}</td>
            <td>{{ request.reason }}</td>
            <td>
              <el-tag :type="statusTagType(request)">
                {{ statusLabel(request) }}
              </el-tag>
            </td>
            <td>{{ request.review_comment || '-' }}</td>
            <td>{{ formatDate(request.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <el-empty
        v-if="!revokeStore.loading && revokeStore.requests.length === 0"
        description="暂无回退申请"
      />
    </section>
  </section>
</template>

<style scoped>
.revoke-apply-band {
  margin-bottom: 20px;
}

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

.revoke-keep-documents {
  align-items: center;
  display: flex;
  gap: 8px;
  margin: 0 0 12px;
}
</style>
