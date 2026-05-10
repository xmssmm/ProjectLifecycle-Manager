<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';

import { DataTable, StatusTag } from '@/components/common';
import { useMainProjectStore } from '@/stores/useMainProjectStore';
import { MAIN_PROJECT_TIMELINE, PROJECT_STATUS_LABELS, type ProjectStatus } from '@/types/projects';

const props = defineProps<{
  projectId: string;
}>();

const mainProjectStore = useMainProjectStore();

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
  </section>
</template>
