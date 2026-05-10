<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { ConfirmDialog, DataTable, StatusTag } from '@/components/common';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMainProjectStore } from '@/stores/useMainProjectStore';
import { MAIN_PROJECT_TIMELINE, PROJECT_STATUS_LABELS, type ProjectStatus } from '@/types/projects';

const props = defineProps<{
  projectId: string;
}>();

const mainProjectStore = useMainProjectStore();
const authStore = useAuthStore();

const project = computed(() => mainProjectStore.currentProject);
const subProjectRows = computed(
  () => mainProjectStore.currentSubProjects as unknown as Record<string, unknown>[],
);
const activeStep = computed(() => {
  if (!project.value) {
    return 0;
  }
  return Math.max(MAIN_PROJECT_TIMELINE.indexOf(project.value.status), 0);
});
const canEditRejectedProject = computed(
  () => project.value?.status === 'rejected' && project.value.creator_id === authStore.user?.id,
);
const canSubmitProject = computed(
  () =>
    Boolean(project.value?.creator_id && project.value.creator_id === authStore.user?.id) &&
    (project.value?.status === 'pending_review' || project.value?.status === 'rejected'),
);
const submitConfirmVisible = ref(false);

const subProjectColumns = [
  { key: 'project_no', label: '子项目编号', minWidth: 180 },
  { key: 'name', label: '子项目名称', minWidth: 220 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'budget', label: '预算', width: 140 },
  { key: 'plan_end_date', label: '计划完成', width: 140 },
];

onMounted(loadProject);

watch(
  () => props.projectId,
  async () => {
    await loadProject();
  },
);

async function loadProject(): Promise<void> {
  await mainProjectStore.fetchMainProjectDetail(props.projectId);
}

async function submitProject(): Promise<void> {
  if (!project.value) {
    return;
  }
  await mainProjectStore.submitMainProject(project.value.id);
  ElMessage.success('主项目已提交审核');
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

function timelineTitle(status: ProjectStatus): string {
  return PROJECT_STATUS_LABELS[status];
}
</script>

<template>
  <section class="admin-page project-page">
    <div class="admin-page__header">
      <div>
        <h2>{{ project?.name ?? '主项目详情' }}</h2>
        <p>{{ project?.project_no ?? '加载中' }}</p>
      </div>
      <router-link :to="{ name: 'main-projects' }">
        <el-button>返回列表</el-button>
      </router-link>
      <router-link
        v-if="project && canEditRejectedProject"
        :to="{ name: 'main-project-edit', params: { id: project.id } }"
      >
        <el-button>编辑</el-button>
      </router-link>
      <el-button
        v-if="project && canSubmitProject"
        type="primary"
        @click="submitConfirmVisible = true"
      >
        提交审核
      </el-button>
    </div>

    <el-skeleton v-if="mainProjectStore.detailLoading && !project" animated />

    <template v-else-if="project">
      <section class="project-detail-band">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="项目编号">{{ project.project_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag :status="project.status" />
          </el-descriptions-item>
          <el-descriptions-item label="部门">{{ project.dept_id }}</el-descriptions-item>
          <el-descriptions-item label="总预算">
            {{ formatMoney(project.total_budget) }}
          </el-descriptions-item>
          <el-descriptions-item label="已付款">
            {{ formatMoney(project.spent_amount) }}
          </el-descriptions-item>
          <el-descriptions-item label="预计完成">
            {{ formatDate(project.expected_finish_date) }}
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="project-detail-band">
        <h3>状态时间线</h3>
        <el-steps :active="activeStep" align-center>
          <el-step
            v-for="status in MAIN_PROJECT_TIMELINE"
            :key="status"
            :title="timelineTitle(status)"
          />
        </el-steps>
      </section>

      <section class="project-detail-band">
        <div class="project-detail-band__header">
          <h3>子项目</h3>
          <span>{{ mainProjectStore.currentSubProjects.length }} 个</span>
        </div>
        <DataTable
          :columns="subProjectColumns"
          :loading="mainProjectStore.detailLoading"
          :page="1"
          :page-size="100"
          :rows="subProjectRows"
          :total="mainProjectStore.currentSubProjects.length"
        >
          <template #status="{ value }">
            <StatusTag :status="String(value)" />
          </template>
          <template #budget="{ value }">
            {{ formatMoney(value) }}
          </template>
          <template #plan_end_date="{ value }">
            {{ formatDate(value) }}
          </template>
        </DataTable>
      </section>
    </template>

    <el-empty v-else description="项目不存在" />

    <ConfirmDialog
      v-model="submitConfirmVisible"
      confirm-text="提交审核"
      message="提交后将通知审核人处理，审核前请确认项目信息无误。"
      title="提交主项目审核"
      @confirm="submitProject"
    />
  </section>
</template>
