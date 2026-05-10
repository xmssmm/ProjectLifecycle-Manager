<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { PhaseProgress } from '@/components/phase';
import { ConfirmDialog, StatusTag } from '@/components/common';
import { usePermission } from '@/composables/usePermission';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSubProjectStore } from '@/stores/useSubProjectStore';
import type { SubProjectMemberRead } from '@/types/projects';

const props = defineProps<{
  subProjectId: string;
}>();

const authStore = useAuthStore();
const subProjectStore = useSubProjectStore();
const { can, hasRole } = usePermission();
const terminateDialogVisible = ref(false);
const terminateReason = ref('');
const memberUserId = ref('');
const memberSubmitting = ref(false);
const submitting = ref(false);

const subProject = computed(() => subProjectStore.currentSubProject);
const canEditRejected = computed(
  () =>
    subProject.value?.status === 'rejected' && subProject.value.creator_id === authStore.user?.id,
);
const canSubmit = computed(
  () =>
    Boolean(subProject.value?.creator_id && subProject.value.creator_id === authStore.user?.id) &&
    (subProject.value?.status === 'pending_review' || subProject.value?.status === 'rejected'),
);
const canReview = computed(
  () =>
    subProject.value?.status === 'pending_review' &&
    can('sub_project.review') &&
    subProject.value.creator_id !== authStore.user?.id,
);
const canTerminate = computed(() => {
  const currentSubProject = subProject.value;
  return (
    Boolean(currentSubProject) &&
    hasRole(['admin', 'dept_manager']) &&
    !['closed', 'terminated'].includes(currentSubProject?.status ?? '')
  );
});
const canManageMembers = computed(() => {
  const currentSubProject = subProject.value;
  return Boolean(
    currentSubProject &&
    authStore.user?.role === 'proj_leader' &&
    currentSubProject.manager_id === authStore.user.id &&
    !['closed', 'terminated'].includes(currentSubProject.status),
  );
});

onMounted(loadSubProject);

watch(
  () => props.subProjectId,
  async () => {
    await loadSubProject();
  },
);

async function loadSubProject(): Promise<void> {
  const loadedSubProject = await subProjectStore.fetchSubProjectDetail(props.subProjectId);
  await subProjectStore.fetchSubProjectMembers(loadedSubProject.id);
}

async function submitSubProject(): Promise<void> {
  if (!subProject.value) {
    return;
  }
  await subProjectStore.submitSubProject(subProject.value.id);
  ElMessage.success('子项目已提交审核');
}

async function terminateSubProject(): Promise<void> {
  if (!subProject.value || !terminateReason.value.trim()) {
    return;
  }
  submitting.value = true;
  try {
    await subProjectStore.terminateSubProject(subProject.value.id, {
      reason: terminateReason.value.trim(),
    });
    ElMessage.success('子项目已中止');
    terminateReason.value = '';
  } finally {
    submitting.value = false;
  }
}

async function addMember(): Promise<void> {
  if (!subProject.value) {
    return;
  }
  const userId = memberUserId.value.trim();
  if (!userId) {
    ElMessage.warning('请输入成员用户 ID');
    return;
  }
  memberSubmitting.value = true;
  try {
    await subProjectStore.addSubProjectMember(subProject.value.id, { user_id: userId });
    memberUserId.value = '';
    ElMessage.success('成员已添加');
  } finally {
    memberSubmitting.value = false;
  }
}

async function removeMember(member: SubProjectMemberRead): Promise<void> {
  if (!subProject.value || !canRemoveMember(member)) {
    return;
  }
  memberSubmitting.value = true;
  try {
    await subProjectStore.removeSubProjectMember(subProject.value.id, member.user_id);
    ElMessage.success('成员已移除');
  } finally {
    memberSubmitting.value = false;
  }
}

function canRemoveMember(member: SubProjectMemberRead): boolean {
  return (
    canManageMembers.value &&
    member.role_in_project !== 'proj_leader' &&
    member.user_id !== authStore.user?.id
  );
}

function memberRoleLabel(member: SubProjectMemberRead): string {
  return member.role_in_project === 'proj_leader' ? '负责人' : '成员';
}

function formatMoney(value: unknown): string {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount)
    ? amount.toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
    : '-';
}

function formatDate(value: unknown): string {
  return typeof value === 'string' && value ? value.slice(0, 10) : '-';
}
</script>

<template>
  <section class="admin-page project-page">
    <div class="admin-page__header">
      <div>
        <h2>{{ subProject?.name ?? '子项目详情' }}</h2>
        <p>{{ subProject?.project_no ?? '加载中' }}</p>
      </div>
      <router-link :to="{ name: 'sub-projects' }">
        <el-button>返回列表</el-button>
      </router-link>
      <router-link
        v-if="subProject && canEditRejected"
        :to="{ name: 'sub-project-edit', params: { id: subProject.id } }"
      >
        <el-button>编辑</el-button>
      </router-link>
      <el-button v-if="subProject && canSubmit" type="primary" @click="submitSubProject">
        提交审核
      </el-button>
      <router-link
        v-if="subProject && canReview"
        :to="{ name: 'sub-project-review', params: { id: subProject.id } }"
      >
        <el-button type="primary">审核</el-button>
      </router-link>
      <el-button
        v-if="subProject && canTerminate"
        data-test="open-terminate"
        type="danger"
        @click="terminateDialogVisible = true"
      >
        中止
      </el-button>
    </div>

    <el-skeleton v-if="subProjectStore.detailLoading && !subProject" animated />

    <template v-else-if="subProject">
      <section class="project-detail-band">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="子项目编号">
            {{ subProject.project_no }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag :status="subProject.status" />
          </el-descriptions-item>
          <el-descriptions-item label="主项目">
            {{ subProject.main_project_id }}
          </el-descriptions-item>
          <el-descriptions-item label="部门">
            {{ subProject.dept_id }}
          </el-descriptions-item>
          <el-descriptions-item label="负责人">
            {{ subProject.manager_id }}
          </el-descriptions-item>
          <el-descriptions-item label="预算">
            {{ formatMoney(subProject.budget) }}
          </el-descriptions-item>
          <el-descriptions-item label="已付款">
            {{ formatMoney(subProject.spent_amount) }}
          </el-descriptions-item>
          <el-descriptions-item label="计划完成">
            {{ formatDate(subProject.plan_end_date) }}
          </el-descriptions-item>
          <el-descriptions-item label="实际完成">
            {{ formatDate(subProject.actual_end_date) }}
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <PhaseProgress :sub-project-id="subProject.id" />

      <section class="project-detail-band">
        <div class="project-detail-band__header">
          <h3>成员</h3>
          <span>{{ subProjectStore.members.length }} 人</span>
        </div>

        <div v-if="canManageMembers" class="project-member-toolbar">
          <el-input
            v-model="memberUserId"
            class="project-member-toolbar__input"
            data-test="member-user-id"
            placeholder="成员用户 ID"
          />
          <el-button
            data-test="add-member"
            :loading="memberSubmitting"
            type="primary"
            @click="addMember"
          >
            添加
          </el-button>
        </div>

        <div class="project-member-table">
          <table>
            <thead>
              <tr>
                <th>用户 ID</th>
                <th>角色</th>
                <th>加入时间</th>
                <th v-if="canManageMembers">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="member in subProjectStore.members" :key="member.id">
                <td>{{ member.user_id }}</td>
                <td>{{ memberRoleLabel(member) }}</td>
                <td>{{ formatDate(member.joined_at) }}</td>
                <td v-if="canManageMembers">
                  <el-button
                    data-test="remove-member"
                    :disabled="!canRemoveMember(member)"
                    :loading="memberSubmitting"
                    size="small"
                    type="danger"
                    @click="removeMember(member)"
                  >
                    移除
                  </el-button>
                </td>
              </tr>
            </tbody>
          </table>
          <el-empty
            v-if="!subProjectStore.membersLoading && subProjectStore.members.length === 0"
            description="暂无成员"
          />
        </div>
      </section>
    </template>

    <el-empty v-else description="子项目不存在" />

    <ConfirmDialog
      v-model="terminateDialogVisible"
      confirm-text="中止"
      message="请输入中止原因，操作会写入审计日志。"
      title="中止子项目"
      type="danger"
      @confirm="terminateSubProject"
    >
      <el-input v-model="terminateReason" data-test="terminate-reason" />
    </ConfirmDialog>
  </section>
</template>
