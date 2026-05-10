<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import { ConfirmDialog, StatusTag } from '@/components/common';
import { useAuthStore } from '@/stores/useAuthStore';
import { useTaskStore } from '@/stores/useTaskStore';
import {
  TASK_STATUS_LABELS,
  TASK_STATUS_OPTIONS,
  type TaskCreatePayload,
  type TaskListQuery,
  type TaskStatus,
} from '@/types/tasks';

import type { TaskRead } from '@/types/tasks';

const authStore = useAuthStore();
const taskStore = useTaskStore();
const createDialogVisible = ref(false);
const quickCompleteDialogVisible = ref(false);
const quickCompleteTarget = ref<TaskRead | null>(null);
const quickCompletingId = ref('');
const submitting = ref(false);
const filterState = reactive({
  assigneeMe: false,
  status: '',
  subProjectId: '',
});
const createForm = reactive({
  executorIds: '',
  executorPlanEndDate: '',
  name: '',
  phaseId: '',
  planEndDate: '',
  subProjectId: '',
});

const taskRows = computed(() => taskStore.tasks);

onMounted(async () => {
  await taskStore.fetchTasks({});
});

async function searchTasks(): Promise<void> {
  await taskStore.fetchTasks(buildQuery());
}

async function submitTask(): Promise<void> {
  const payload = buildCreatePayload();
  if (!payload) {
    return;
  }

  submitting.value = true;
  try {
    await taskStore.createTask(payload);
    resetCreateForm();
    createDialogVisible.value = false;
  } finally {
    submitting.value = false;
  }
}

function currentExecutor(task: TaskRead) {
  return task.executors.find((executor) => executor.user_id === authStore.user?.id);
}

function canQuickComplete(task: TaskRead): boolean {
  const executor = currentExecutor(task);
  return Boolean(executor) && executor?.status !== 'completed';
}

function openQuickComplete(task: TaskRead): void {
  if (!canQuickComplete(task)) {
    return;
  }
  quickCompleteTarget.value = task;
  quickCompleteDialogVisible.value = true;
}

async function confirmQuickComplete(): Promise<void> {
  const task = quickCompleteTarget.value;
  if (!task) {
    return;
  }
  quickCompletingId.value = task.id;
  try {
    await taskStore.completeTask(task.id);
    quickCompleteDialogVisible.value = false;
    quickCompleteTarget.value = null;
  } finally {
    quickCompletingId.value = '';
  }
}

function buildQuery(): TaskListQuery {
  const query: TaskListQuery = {};
  const subProjectId = filterState.subProjectId.trim();
  if (subProjectId) {
    query.subProjectId = subProjectId;
  }
  if (filterState.status) {
    query.status = filterState.status as TaskStatus;
  }
  if (filterState.assigneeMe) {
    query.assignee = 'me';
  }
  return query;
}

function buildCreatePayload(): TaskCreatePayload | null {
  const executorIds = createForm.executorIds
    .split(/[\s,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);

  if (
    !createForm.name.trim() ||
    !createForm.subProjectId.trim() ||
    !createForm.phaseId.trim() ||
    !createForm.planEndDate ||
    !createForm.executorPlanEndDate ||
    executorIds.length === 0
  ) {
    return null;
  }

  return {
    executors: executorIds.map((userId) => ({
      plan_end_date: createForm.executorPlanEndDate,
      user_id: userId,
    })),
    name: createForm.name.trim(),
    phase_id: createForm.phaseId.trim(),
    plan_end_date: createForm.planEndDate,
    sub_project_id: createForm.subProjectId.trim(),
  };
}

function resetCreateForm(): void {
  createForm.executorIds = '';
  createForm.executorPlanEndDate = '';
  createForm.name = '';
  createForm.phaseId = '';
  createForm.planEndDate = '';
  createForm.subProjectId = '';
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
        <h2>任务管理</h2>
        <p>按子项目、状态和负责人快速定位任务，并分配执行人。</p>
      </div>
      <el-button data-test="open-create-task" type="primary" @click="createDialogVisible = true">
        新建任务
      </el-button>
    </div>

    <section class="task-filter-band">
      <label class="task-field">
        <span>子项目 ID</span>
        <el-input
          v-model="filterState.subProjectId"
          data-test="filter-sub-project"
          placeholder="输入子项目 ID"
        />
      </label>
      <label class="task-field">
        <span>状态</span>
        <el-select v-model="filterState.status" data-test="filter-status">
          <el-option
            v-for="option in TASK_STATUS_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          >
            {{ option.label }}
          </el-option>
        </el-select>
      </label>
      <el-checkbox
        v-model="filterState.assigneeMe"
        class="task-check"
        data-test="filter-assignee-me"
      >
        只看分配给我
      </el-checkbox>
      <el-button data-test="search-tasks" :loading="taskStore.loading" @click="searchTasks">
        查询
      </el-button>
    </section>

    <section class="admin-page__table task-table-band">
      <table class="task-table">
        <thead>
          <tr>
            <th>任务编号</th>
            <th>任务名称</th>
            <th>状态</th>
            <th>子项目</th>
            <th>阶段</th>
            <th>计划完成</th>
            <th>执行人</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in taskRows" :key="task.id">
            <td>{{ task.task_no }}</td>
            <td>{{ task.name }}</td>
            <td>
              <StatusTag :status="task.status" />
              <span class="sr-only">{{ statusLabel(task.status) }}</span>
            </td>
            <td>{{ task.sub_project_id }}</td>
            <td>{{ task.phase_id }}</td>
            <td>{{ formatDate(task.plan_end_date) }}</td>
            <td>{{ task.executors.map((executor) => executor.user_id).join(', ') }}</td>
            <td>
              <router-link :to="{ name: 'task-detail', params: { id: task.id } }">
                <el-button size="small">查看</el-button>
              </router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="task-mobile-list">
        <article v-for="task in taskRows" :key="task.id" class="task-mobile-card">
          <div class="task-mobile-card__header">
            <div>
              <span>{{ task.task_no }}</span>
              <h3>{{ task.name }}</h3>
            </div>
            <StatusTag :status="task.status" />
          </div>
          <dl class="task-mobile-card__meta">
            <div>
              <dt>子项目</dt>
              <dd>{{ task.sub_project_id }}</dd>
            </div>
            <div>
              <dt>阶段</dt>
              <dd>{{ task.phase_id }}</dd>
            </div>
            <div>
              <dt>计划完成</dt>
              <dd>{{ formatDate(task.plan_end_date) }}</dd>
            </div>
          </dl>
          <div class="task-mobile-card__actions">
            <router-link :to="{ name: 'task-detail', params: { id: task.id } }">
              <el-button size="small">查看</el-button>
            </router-link>
            <el-button
              v-if="canQuickComplete(task)"
              class="mobile-only-action"
              :data-test="`quick-complete-task-${task.id}`"
              :loading="quickCompletingId === task.id"
              size="small"
              type="primary"
              @click="openQuickComplete(task)"
            >
              完成
            </el-button>
          </div>
        </article>
      </div>
      <el-empty v-if="!taskStore.loading && taskRows.length === 0" description="暂无任务" />
    </section>

    <el-dialog v-model="createDialogVisible" title="新建任务" width="640px">
      <el-form label-position="top" class="task-form" @submit.prevent>
        <el-form-item label="任务名称">
          <el-input v-model="createForm.name" data-test="task-name" placeholder="输入任务名称" />
        </el-form-item>
        <el-form-item label="子项目 ID">
          <el-input
            v-model="createForm.subProjectId"
            data-test="task-sub-project"
            placeholder="输入子项目 ID"
          />
        </el-form-item>
        <el-form-item label="阶段 ID">
          <el-input v-model="createForm.phaseId" data-test="task-phase" placeholder="输入阶段 ID" />
        </el-form-item>
        <el-form-item label="任务计划完成日期">
          <el-input v-model="createForm.planEndDate" data-test="task-plan-end" type="date" />
        </el-form-item>
        <el-form-item label="执行人用户 ID">
          <el-input
            v-model="createForm.executorIds"
            data-test="task-executor-ids"
            placeholder="多个用户用逗号分隔"
          />
        </el-form-item>
        <el-form-item label="执行人计划完成日期">
          <el-input
            v-model="createForm.executorPlanEndDate"
            data-test="task-executor-plan-end"
            type="date"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="project-form-actions">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button
            data-test="submit-task"
            :loading="submitting"
            type="primary"
            @click="submitTask"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <ConfirmDialog
      v-model="quickCompleteDialogVisible"
      confirm-data-test="confirm-quick-complete"
      confirm-text="完成任务"
      data-test="quick-complete-confirm"
      :message="`确认完成任务“${quickCompleteTarget?.name ?? ''}”？`"
      title="完成任务"
      type="primary"
      @confirm="confirmQuickComplete"
    />
  </section>
</template>
