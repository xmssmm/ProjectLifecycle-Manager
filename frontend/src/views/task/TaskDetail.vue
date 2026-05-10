<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';

import { StatusTag } from '@/components/common';
import { useAuthStore } from '@/stores/useAuthStore';
import { useTaskStore } from '@/stores/useTaskStore';
import { TASK_STATUS_LABELS, type TaskStatus } from '@/types/tasks';

const props = defineProps<{
  taskId: string;
}>();

const authStore = useAuthStore();
const taskStore = useTaskStore();
const task = computed(() => taskStore.currentTask);
const currentExecutor = computed(() =>
  task.value?.executors.find((executor) => executor.user_id === authStore.user?.id),
);
const canComplete = computed(
  () => Boolean(currentExecutor.value) && currentExecutor.value?.status !== 'completed',
);

onMounted(loadTask);

watch(
  () => props.taskId,
  async () => {
    await loadTask();
  },
);

async function loadTask(): Promise<void> {
  await taskStore.fetchTaskDetail(props.taskId);
}

async function completeCurrentTask(): Promise<void> {
  if (!task.value) {
    return;
  }
  await taskStore.completeTask(task.value.id);
}

function formatDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : '-';
}

function statusLabel(status: TaskStatus): string {
  return TASK_STATUS_LABELS[status];
}
</script>

<template>
  <section class="admin-page project-page task-page">
    <div class="admin-page__header">
      <div>
        <h2>{{ task?.name ?? '任务详情' }}</h2>
        <p>{{ task?.task_no ?? '加载中' }}</p>
      </div>
      <div class="row-actions">
        <router-link :to="{ name: 'tasks' }">
          <el-button>返回列表</el-button>
        </router-link>
        <el-button
          v-if="task && canComplete"
          data-test="complete-task"
          :loading="taskStore.detailLoading"
          type="primary"
          @click="completeCurrentTask"
        >
          完成任务
        </el-button>
      </div>
    </div>

    <el-skeleton v-if="taskStore.detailLoading && !task" animated />

    <template v-else-if="task">
      <section class="project-detail-band task-summary">
        <div>
          <span class="task-summary__label">状态</span>
          <div class="task-summary__value">
            <StatusTag :status="task.status" />
            <span data-test="task-status-code">{{ task.status }}</span>
            <span class="sr-only">{{ statusLabel(task.status) }}</span>
          </div>
        </div>
        <div>
          <span class="task-summary__label">子项目</span>
          <strong>{{ task.sub_project_id }}</strong>
        </div>
        <div>
          <span class="task-summary__label">阶段</span>
          <strong>{{ task.phase_id }}</strong>
        </div>
        <div>
          <span class="task-summary__label">计划完成</span>
          <strong>{{ formatDate(task.plan_end_date) }}</strong>
        </div>
      </section>

      <section class="project-detail-band">
        <div class="project-detail-band__header">
          <h3>执行人</h3>
          <span>{{ task.executors.length }} 人</span>
        </div>
        <div class="project-member-table">
          <table>
            <thead>
              <tr>
                <th>用户 ID</th>
                <th>状态</th>
                <th>计划完成</th>
                <th>实际完成</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="executor in task.executors" :key="executor.id">
                <td>{{ executor.user_id }}</td>
                <td>
                  <StatusTag :status="executor.status" />
                  <span class="task-status-code">{{ executor.status }}</span>
                </td>
                <td>{{ formatDate(executor.plan_end_date) }}</td>
                <td>{{ formatDate(executor.actual_end_date) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="task-executor-cards">
          <article
            v-for="executor in task.executors"
            :key="executor.id"
            class="task-executor-card"
            data-test="task-executor-mobile-card"
          >
            <div>
              <span>用户 ID</span>
              <strong>{{ executor.user_id }}</strong>
            </div>
            <div>
              <span>状态</span>
              <strong>
                <StatusTag :status="executor.status" />
                <span class="task-status-code">{{ executor.status }}</span>
              </strong>
            </div>
            <div>
              <span>计划完成</span>
              <strong>{{ formatDate(executor.plan_end_date) }}</strong>
            </div>
            <div>
              <span>实际完成</span>
              <strong>{{ formatDate(executor.actual_end_date) }}</strong>
            </div>
          </article>
        </div>
      </section>
    </template>

    <el-empty v-else description="任务不存在" />
  </section>
</template>
