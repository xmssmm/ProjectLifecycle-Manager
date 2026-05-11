<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue';
import { computed, onMounted, watch } from 'vue';

import DashboardChart from '@/components/dashboard/DashboardChart.vue';
import { StatusTag } from '@/components/common';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDashboardStore } from '@/stores/useDashboardStore';
import type { DashboardListItem, DashboardRoleScope } from '@/types/dashboard';
import { ROLE_LABELS } from '@/types/users';
import { formatUserDateTime } from '@/utils/timezone';

const METRIC_LABELS: Record<string, string> = {
  api_error_rate_source: '接口错误率来源',
  current_month_new_projects: '本月新增项目',
  current_month_payment_total: '本月付款金额',
  due_or_overdue_tasks: '临近/逾期任务',
  due_soon_tasks: '7日内到期任务',
  main_projects: '主项目数',
  managed_sub_projects: '负责子项目',
  over_budget_sub_projects: '超预算子项目',
  participating_sub_projects: '参与子项目',
  phases_to_promote: '待推进阶段',
  todo_tasks: '待办任务',
  total_budget: '总预算',
  total_main_projects: '主项目总数',
  total_paid: '累计付款',
  total_users: '用户总数',
};

const CHART_LABELS: Record<string, string> = {
  department_project_counts: '部门项目分布',
  main_project_status: '主项目状态',
  paid_vs_budget: '付款与预算',
  sub_project_status: '子项目状态',
  todo_tasks_by_due_date: '待办截止日期',
};

const LIST_LABELS: Record<string, string> = {
  over_budget_sub_projects: '超预算子项目',
  participating_sub_projects: '参与子项目',
  phases_to_promote: '待推进阶段',
  sub_project_payment_ranking: '子项目付款排行',
  unpaid_sub_projects: '未付款子项目',
};

const EXCLUDED_LIST_FIELDS = new Set(['id', 'name', 'phase_no', 'status', 'sub_project_id']);

const authStore = useAuthStore();
const dashboardStore = useDashboardStore();

const roleScope = computed<DashboardRoleScope>(() => authStore.user?.role ?? 'proj_member');
const dashboard = computed(() => dashboardStore.dashboard);
const roleTitle = computed(() => ROLE_LABELS[dashboard.value?.role_scope ?? roleScope.value]);
const metricEntries = computed(() => Object.entries(dashboard.value?.metrics ?? {}));
const chartEntries = computed(() =>
  Object.entries(dashboard.value?.charts ?? {}).filter(([, points]) => points.length > 0),
);
const listEntries = computed(() => Object.entries(dashboard.value?.lists ?? {}));

onMounted(() => {
  void refreshDashboard();
});

watch(roleScope, () => {
  void refreshDashboard();
});

async function refreshDashboard(): Promise<void> {
  try {
    await dashboardStore.fetchDashboard(roleScope.value);
  } catch {
    // The store keeps the displayable error message for the alert.
  }
}

function labelForMetric(key: string): string {
  return METRIC_LABELS[key] ?? humanizeKey(key);
}

function labelForChart(key: string): string {
  return CHART_LABELS[key] ?? humanizeKey(key);
}

function labelForList(key: string): string {
  return LIST_LABELS[key] ?? humanizeKey(key);
}

function chartType(key: string): 'bar' | 'pie' {
  return key.includes('status') || key === 'paid_vs_budget' ? 'pie' : 'bar';
}

function listItemTitle(item: DashboardListItem): string {
  return String(item.name ?? item.phase_no ?? item.id ?? '-');
}

function listItemRoute(item: DashboardListItem): string {
  const subProjectId = item.sub_project_id ?? item.id;
  return typeof subProjectId === 'string' && subProjectId ? `/sub-projects/${subProjectId}` : '/';
}

function listItemFields(item: DashboardListItem): [string, string][] {
  return Object.entries(item)
    .filter(([key, value]) => !EXCLUDED_LIST_FIELDS.has(key) && value !== null)
    .map(([key, value]) => [labelForMetric(key), String(value)]);
}

function formatGeneratedAt(value: string | null): string {
  return formatUserDateTime(value, authStore.user?.timezone);
}

function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ');
}
</script>

<template>
  <section class="admin-page dashboard-page">
    <div class="admin-page__header">
      <div>
        <h2 data-test="dashboard-role-title">{{ roleTitle }}驾驶舱</h2>
        <p>
          更新时间 {{ formatGeneratedAt(dashboardStore.lastLoadedAt) }}，缓存
          {{ dashboard?.cache_ttl_seconds ?? 300 }} 秒
        </p>
      </div>
      <el-button :icon="Refresh" :loading="dashboardStore.loading" type="primary" @click="refreshDashboard">
        刷新
      </el-button>
    </div>

    <el-alert
      v-if="dashboardStore.error"
      :closable="false"
      :title="dashboardStore.error"
      type="error"
    />

    <el-skeleton :loading="dashboardStore.loading && !dashboard" animated>
      <template #default>
        <dl class="dashboard-metrics">
          <div
            v-for="[key, value] in metricEntries"
            :key="key"
            class="dashboard-metric"
            :data-test="`dashboard-metric-${key}`"
          >
            <dt>{{ labelForMetric(key) }}</dt>
            <dd>{{ value }}</dd>
          </div>
        </dl>

        <section class="dashboard-grid">
          <article
            v-for="[key, points] in chartEntries"
            :key="key"
            class="dashboard-panel"
            :data-test="`dashboard-chart-${key}`"
          >
            <div class="project-detail-band__header">
              <h3>{{ labelForChart(key) }}</h3>
              <span>{{ points.length }} 项</span>
            </div>
            <DashboardChart :points="points" :title="labelForChart(key)" :type="chartType(key)" />
          </article>
        </section>

        <section class="dashboard-list-grid">
          <article
            v-for="[key, items] in listEntries"
            :key="key"
            class="dashboard-panel"
            :data-test="`dashboard-list-${key}`"
          >
            <div class="project-detail-band__header">
              <h3>{{ labelForList(key) }}</h3>
              <span>{{ items.length }} 项</span>
            </div>
            <div v-if="items.length > 0" class="dashboard-list">
              <router-link
                v-for="item in items"
                :key="String(item.id ?? item.name)"
                class="dashboard-list-item"
                :to="listItemRoute(item)"
              >
                <div>
                  <strong>{{ listItemTitle(item) }}</strong>
                  <p v-if="listItemFields(item).length > 0">
                    <span v-for="[field, value] in listItemFields(item)" :key="field">
                      {{ field }}：{{ value }}
                    </span>
                  </p>
                </div>
                <StatusTag v-if="item.status" :status="String(item.status)" />
              </router-link>
            </div>
            <el-empty v-else description="暂无数据" />
          </article>
        </section>
      </template>
    </el-skeleton>
  </section>
</template>
