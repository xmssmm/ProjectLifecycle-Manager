<script setup lang="ts">
import { Bell } from '@element-plus/icons-vue';
import { storeToRefs } from 'pinia';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { useNotificationStore } from '@/stores/useNotificationStore';
import type { NotificationRead } from '@/types/notifications';

const store = useNotificationStore();
const { loading, notifications, unreadCount } = storeToRefs(store);
const panelOpen = ref(false);

const badgeValue = computed(() => (unreadCount.value > 99 ? '99+' : unreadCount.value));

onMounted(() => {
  void store.fetchUnreadCount();
  store.startUnreadPolling();
});

onBeforeUnmount(() => {
  store.stopUnreadPolling();
});

async function togglePanel() {
  panelOpen.value = !panelOpen.value;
  if (panelOpen.value) {
    await store.fetchNotifications({ page: 1, pageSize: 10 });
  }
}

async function markRead(notification: NotificationRead) {
  await store.markRead(notification.id);
}

async function markAllRead() {
  await store.markAllRead();
}

function scenarioLabel(notification: NotificationRead): string {
  return (
    {
      handover_completed: '负责人转交',
      over_budget_warning: '超预算预警',
      payment_created: '付款通知',
      phase_promoted: '环节推进',
      project_pending_review: '项目待审核',
      project_review_result: '审核结果',
      revoke_request_pending: '撤销待审核',
      revoke_result: '撤销结果',
      task_assigned: '任务指派',
      task_due_today: '任务到期',
      task_overdue: '任务逾期',
      task_overdue_escalation: '逾期升级',
    }[notification.scenario] ?? notification.scenario
  );
}

function notificationSummary(notification: NotificationRead): string {
  const payload = notification.payload;
  const projectName = valueText(payload.project_name);
  const projectNo = valueText(payload.project_no);
  const taskNo = valueText(payload.task_no);
  const amount = valueText(payload.amount);
  const phaseNo = valueText(payload.phase_no ?? payload.completed_phase_no);
  const decision = decisionLabel(valueText(payload.decision));

  if (taskNo) {
    return `任务 ${taskNo}`;
  }
  if (notification.scenario === 'payment_created' && amount) {
    return `新增付款 ${amount}`;
  }
  if (notification.scenario === 'over_budget_warning') {
    return amount ? `付款超预算 ${amount}` : '付款超预算';
  }
  if (notification.scenario.startsWith('revoke') && phaseNo) {
    return `环节 ${phaseNo}${decision ? ` ${decision}` : ''}`;
  }
  if (notification.scenario === 'phase_promoted' && phaseNo) {
    return `环节 ${phaseNo} 已推进`;
  }
  if (projectName || projectNo) {
    return [projectNo, projectName, decision].filter(Boolean).join(' ');
  }
  return `来源 ${notification.source_id}`;
}

function notificationTarget(notification: NotificationRead): string | null {
  const payload = notification.payload;
  const taskId = valueText(payload.task_id);
  if (taskId) {
    return `/tasks/${taskId}`;
  }

  if (notification.scenario === 'revoke_request_pending') {
    return '/revoke-requests/review';
  }

  const subProjectId = valueText(payload.sub_project_id);
  if (notification.scenario === 'payment_created' && subProjectId) {
    return `/sub-projects/${subProjectId}/payments`;
  }
  if (subProjectId) {
    return `/sub-projects/${subProjectId}`;
  }

  if (notification.scenario === 'handover_completed') {
    return `/sub-projects/${notification.source_id}`;
  }

  if (notification.scenario === 'project_pending_review') {
    return `/main-projects/${notification.source_id}/review`;
  }
  if (notification.scenario === 'project_review_result') {
    return `/main-projects/${notification.source_id}`;
  }
  return null;
}

function formatCreatedAt(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
  });
}

function valueText(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return null;
}

function decisionLabel(value: string | null): string | null {
  if (value === 'approve' || value === 'approved') {
    return '已通过';
  }
  if (value === 'reject' || value === 'rejected') {
    return '已驳回';
  }
  return value;
}
</script>

<template>
  <div class="notification-center">
    <el-badge :hidden="unreadCount === 0" :value="badgeValue">
      <el-button
        circle
        :icon="Bell"
        aria-label="通知中心"
        data-test="notification-trigger"
        @click="togglePanel"
      />
    </el-badge>

    <section
      v-if="panelOpen"
      class="notification-center__panel notification-center__panel--touch"
      data-test="notification-panel"
    >
      <header class="notification-center__header">
        <div>
          <strong>通知中心</strong>
          <span>{{ unreadCount }} 条未读</span>
        </div>
        <el-button
          text
          type="primary"
          :disabled="unreadCount === 0"
          data-test="mark-all-notifications-read"
          @click="markAllRead"
        >
          全部已读
        </el-button>
      </header>

      <el-empty v-if="!loading && notifications.length === 0" description="暂无通知" />
      <div v-else class="notification-center__list">
        <article
          v-for="notification in notifications"
          :key="notification.id"
          class="notification-center__item"
          :class="{ 'notification-center__item--unread': notification.read_at === null }"
          data-test="notification-item"
        >
          <div class="notification-center__item-main">
            <div class="notification-center__item-title">
              <el-tag v-if="notification.read_at === null" type="danger">未读</el-tag>
              <span>{{ scenarioLabel(notification) }}</span>
            </div>
            <p>{{ notificationSummary(notification) }}</p>
            <time>{{ formatCreatedAt(notification.created_at) }}</time>
          </div>
          <div class="notification-center__item-actions">
            <router-link
              v-if="notificationTarget(notification)"
              :to="notificationTarget(notification)!"
              :data-test="`notification-link-${notification.id}`"
            >
              查看
            </router-link>
            <el-button
              v-if="notification.read_at === null"
              text
              type="primary"
              :data-test="`mark-notification-read-${notification.id}`"
              @click="markRead(notification)"
            >
              已读
            </el-button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
