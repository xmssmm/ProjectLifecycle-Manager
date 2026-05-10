<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { ConfirmDialog } from '@/components/common';
import { useUserStore } from '@/stores/useUserStore';
import type { SubProjectRead } from '@/types/projects';

const userStore = useUserStore();
const fromUserId = ref('');
const toUserId = ref('');
const reason = ref('');
const selectedProjectIds = ref<string[]>([]);
const confirmVisible = ref(false);
const validationMessage = ref('');

const leaderOptions = computed(() =>
  userStore.users.filter((user) => user.role === 'proj_leader' && user.status === 'active'),
);
const toLeaderOptions = computed(() =>
  leaderOptions.value.filter((user) => user.id !== fromUserId.value),
);
const selectedProjects = computed(() =>
  userStore.activeSubProjects.filter((project) => selectedProjectIds.value.includes(project.id)),
);
const confirmMessage = computed(
  () =>
    `将 ${selectedProjectIds.value.length} 个在途子项目转交给 ${leaderName(toUserId.value)}。请确认原因已填写清楚。`,
);

onMounted(async () => {
  await userStore.fetchUsers({ page: 1, pageSize: 100, role: 'proj_leader' });
});

watch(fromUserId, async (userId) => {
  selectedProjectIds.value = [];
  toUserId.value = '';
  validationMessage.value = '';
  if (!userId) {
    userStore.activeSubProjects = [];
    return;
  }
  await userStore.fetchActiveSubProjectsForLeader(userId);
});

function openConfirm(): void {
  validationMessage.value = validateForm();
  if (validationMessage.value) {
    return;
  }
  confirmVisible.value = true;
}

async function submitHandover(): Promise<void> {
  if (validationMessage.value) {
    return;
  }
  await userStore.batchHandoverSubProjects(
    fromUserId.value,
    selectedProjectIds.value.map((projectId) => ({
      reason: reason.value.trim(),
      sub_project_id: projectId,
      to_user_id: toUserId.value,
    })),
  );
  ElMessage.success('负责人转交已完成');
  confirmVisible.value = false;
  selectedProjectIds.value = [];
  reason.value = '';
}

function validateForm(): string {
  if (!fromUserId.value) {
    return '请选择原负责人';
  }
  if (!selectedProjectIds.value.length) {
    return '请选择要转交的子项目';
  }
  if (!toUserId.value) {
    return '请选择新负责人';
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

function leaderName(userId: string): string {
  return leaderOptions.value.find((user) => user.id === userId)?.username ?? '-';
}

function formatMoney(value: unknown): string {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount)
    ? amount.toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
    : '-';
}

function formatProjectStatus(project: SubProjectRead): string {
  return project.status === 'not_started'
    ? '未开始'
    : project.status === 'in_progress'
      ? '进行中'
      : '已完成';
}
</script>

<template>
  <section class="admin-page project-page">
    <div class="admin-page__header">
      <div>
        <h2>负责人转交</h2>
        <p>处理项目负责人离职、调岗时的在途子项目交接。</p>
      </div>
      <router-link :to="{ name: 'admin-handover-history' }">
        <el-button>转交历史</el-button>
      </router-link>
    </div>

    <section class="project-form-band handover-panel">
      <el-form label-width="112px">
        <el-form-item label="原负责人">
          <el-select
            v-model="fromUserId"
            data-test="from-user"
            filterable
            placeholder="选择原负责人"
          >
            <el-option
              v-for="user in leaderOptions"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="新负责人">
          <el-select v-model="toUserId" data-test="to-user" filterable placeholder="选择新负责人">
            <el-option
              v-for="user in toLeaderOptions"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="转交原因">
          <el-input
            v-model="reason"
            data-test="handover-reason"
            maxlength="500"
            placeholder="请输入转交原因"
            show-word-limit
            type="textarea"
          />
        </el-form-item>
      </el-form>

      <p v-if="validationMessage" class="form-error">{{ validationMessage }}</p>
    </section>

    <section class="project-detail-band">
      <div class="project-detail-band__header">
        <h3>在途子项目</h3>
        <span>{{ userStore.activeSubProjects.length }} 个</span>
      </div>

      <div class="project-member-table">
        <table v-if="userStore.activeSubProjects.length">
          <thead>
            <tr>
              <th>选择</th>
              <th>子项目编号</th>
              <th>子项目名称</th>
              <th>状态</th>
              <th>预算</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="project in userStore.activeSubProjects" :key="project.id">
              <td>
                <el-checkbox
                  data-test="select-sub-project"
                  :model-value="selectedProjectIds.includes(project.id)"
                  @update:model-value="toggleProject(project.id, Boolean($event))"
                />
              </td>
              <td>{{ project.project_no }}</td>
              <td>{{ project.name }}</td>
              <td>{{ formatProjectStatus(project) }}</td>
              <td>{{ formatMoney(project.budget) }}</td>
            </tr>
          </tbody>
        </table>
        <el-empty v-else :description="fromUserId ? '暂无在途子项目' : '请选择原负责人'" />
      </div>

      <div class="project-form-actions">
        <el-button
          data-test="submit-handover"
          :loading="userStore.handoverSubmitting"
          type="primary"
          @click="openConfirm"
        >
          批量转交
        </el-button>
      </div>
    </section>

    <ConfirmDialog
      v-model="confirmVisible"
      confirm-text="确认转交"
      :message="confirmMessage"
      title="确认转交"
      type="warning"
      @confirm="submitHandover"
    >
      <ul class="handover-confirm-list">
        <li v-for="project in selectedProjects" :key="project.id">
          {{ project.project_no }} {{ project.name }}
        </li>
      </ul>
    </ConfirmDialog>
  </section>
</template>
