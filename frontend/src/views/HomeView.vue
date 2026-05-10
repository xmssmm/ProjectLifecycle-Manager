<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { StatusTag } from '@/components/common';
import { useTaskStore } from '@/stores/useTaskStore';
import type { TaskRead } from '@/types/tasks';

const taskStore = useTaskStore();

const unfinishedTasks = computed(() =>
  [...taskStore.tasks]
    .filter((task) => task.status !== 'completed')
    .sort((left, right) => compareTaskDueDate(left, right)),
);
const overdueTasks = computed(() =>
  unfinishedTasks.value.filter((task) => task.status === 'overdue'),
);
const nextDueTask = computed(() => unfinishedTasks.value[0] ?? null);

onMounted(async () => {
  await taskStore.fetchTasks({ assignee: 'me' });
});

function compareTaskDueDate(left: TaskRead, right: TaskRead): number {
  const dateCompared = left.plan_end_date.localeCompare(right.plan_end_date);
  return dateCompared === 0 ? left.created_at.localeCompare(right.created_at) : dateCompared;
}

function formatDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : '-';
}
</script>

<template>
  <section class="admin-page workspace-page">
    <div class="admin-page__header">
      <div>
        <h2>工作台</h2>
        <p>优先处理分配给我的未完成任务，按计划完成日期排序。</p>
      </div>
      <router-link :to="{ name: 'tasks' }">
        <el-button>全部任务</el-button>
      </router-link>
    </div>

    <dl class="workspace-metrics">
      <div>
        <dt>待处理任务</dt>
        <dd>{{ unfinishedTasks.length }}</dd>
      </div>
      <div>
        <dt>已逾期</dt>
        <dd>{{ overdueTasks.length }}</dd>
      </div>
      <div>
        <dt>最近到期</dt>
        <dd class="workspace-metrics__date">{{ formatDate(nextDueTask?.plan_end_date) }}</dd>
      </div>
    </dl>

    <section class="workspace-task-panel">
      <div class="project-detail-band__header">
        <h3>我的待办</h3>
        <span>{{ unfinishedTasks.length }} 项</span>
      </div>

      <div v-if="unfinishedTasks.length > 0" class="workspace-task-list">
        <article
          v-for="task in unfinishedTasks"
          :key="task.id"
          class="workspace-task-item"
          data-test="workbench-task-row"
        >
          <div>
            <span class="workspace-task-item__no">{{ task.task_no }}</span>
            <h4>{{ task.name }}</h4>
            <p>{{ task.sub_project_id }} / {{ task.phase_id }}</p>
          </div>
          <div class="workspace-task-item__meta">
            <StatusTag :status="task.status" />
            <span>{{ formatDate(task.plan_end_date) }}</span>
            <router-link
              data-test="task-detail-link"
              :to="{ name: 'task-detail', params: { id: task.id } }"
            >
              <el-button size="small" type="primary">处理</el-button>
            </router-link>
          </div>
        </article>
      </div>

      <el-empty v-else description="暂无未完成任务" />
    </section>
  </section>
</template>
