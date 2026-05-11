<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import { useAuthStore } from '@/stores/useAuthStore';
import { useAuditLogStore } from '@/stores/useAuditLogStore';
import type { AuditLogListQuery, AuditLogRead } from '@/types/auditLogs';
import { formatUserDateTime } from '@/utils/timezone';

const authStore = useAuthStore();
const auditLogStore = useAuditLogStore();
const filters = reactive({
  action: '',
  actorId: '',
  createdFrom: '',
  createdTo: '',
  targetId: '',
  targetType: '',
});
const selectedLog = ref<AuditLogRead | null>(null);
const detailVisible = ref(false);

const hasLogs = computed(() => auditLogStore.auditLogs.length > 0);

onMounted(async () => {
  await auditLogStore.fetchAuditLogs({ page: 1, pageSize: 20 });
});

async function searchLogs(page = 1, pageSize = auditLogStore.pageSize): Promise<void> {
  await auditLogStore.fetchAuditLogs({
    ...cleanFilters(),
    page,
    pageSize,
  });
}

async function resetFilters(): Promise<void> {
  filters.action = '';
  filters.actorId = '';
  filters.createdFrom = '';
  filters.createdTo = '';
  filters.targetId = '';
  filters.targetType = '';
  await searchLogs(1, auditLogStore.pageSize);
}

function openDetail(log: AuditLogRead): void {
  selectedLog.value = log;
  detailVisible.value = true;
}

function cleanFilters(): Omit<AuditLogListQuery, 'page' | 'pageSize'> {
  return {
    action: cleanValue(filters.action),
    actorId: cleanValue(filters.actorId),
    createdFrom: cleanValue(filters.createdFrom),
    createdTo: cleanValue(filters.createdTo),
    targetId: cleanValue(filters.targetId),
    targetType: cleanValue(filters.targetType),
  };
}

function cleanValue(value: string): string | undefined {
  const cleaned = value.trim();
  return cleaned || undefined;
}

function formatDate(value: string): string {
  return formatUserDateTime(value, authStore.user?.timezone);
}

function formatJson(value: Record<string, unknown> | undefined): string {
  return JSON.stringify(value ?? {}, null, 2);
}
</script>

<template>
  <section class="admin-page audit-log-page">
    <div class="admin-page__header">
      <div>
        <h2>审计日志</h2>
        <p>按操作人、动作、目标和时间范围查询敏感操作记录。</p>
      </div>
    </div>

    <section class="audit-log-filter">
      <label>
        操作人 ID
        <el-input v-model="filters.actorId" data-test="audit-filter-actor" />
      </label>
      <label>
        动作
        <el-input v-model="filters.action" data-test="audit-filter-action" />
      </label>
      <label>
        目标类型
        <el-input v-model="filters.targetType" data-test="audit-filter-target-type" />
      </label>
      <label>
        目标 ID
        <el-input v-model="filters.targetId" data-test="audit-filter-target-id" />
      </label>
      <label>
        开始时间
        <el-input v-model="filters.createdFrom" data-test="audit-filter-created-from" />
      </label>
      <label>
        结束时间
        <el-input v-model="filters.createdTo" data-test="audit-filter-created-to" />
      </label>
      <div class="audit-log-filter__actions">
        <el-button data-test="search-audit-logs" type="primary" @click="searchLogs(1)">
          查询
        </el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <section class="admin-page__table audit-log-table">
      <table v-if="hasLogs">
        <thead>
          <tr>
            <th>时间</th>
            <th>动作</th>
            <th>操作人</th>
            <th>目标</th>
            <th>Request ID</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in auditLogStore.auditLogs" :key="log.id" data-test="audit-log-row">
            <td>{{ formatDate(log.created_at) }}</td>
            <td>{{ log.action }}</td>
            <td>{{ log.actor_id ?? '-' }}</td>
            <td>{{ log.target_type }} / {{ log.target_id }}</td>
            <td>{{ log.request_id ?? '-' }}</td>
            <td>
              <el-button data-test="open-audit-detail" size="small" @click="openDetail(log)">
                详情
              </el-button>
            </td>
          </tr>
        </tbody>
      </table>
      <el-empty v-else-if="!auditLogStore.loading" description="暂无审计日志" />
      <el-pagination
        :current-page="auditLogStore.page"
        layout="prev, pager, next, sizes, total"
        :page-size="auditLogStore.pageSize"
        :total="auditLogStore.total"
        @current-change="searchLogs($event, auditLogStore.pageSize)"
        @size-change="searchLogs(1, $event)"
      />
    </section>

    <el-dialog v-model="detailVisible" title="审计详情" width="760px">
      <section v-if="selectedLog" class="audit-log-detail">
        <div>
          <h3>Before</h3>
          <pre>{{ formatJson(selectedLog.before_state) }}</pre>
        </div>
        <div>
          <h3>After</h3>
          <pre>{{ formatJson(selectedLog.after_state) }}</pre>
        </div>
        <div>
          <h3>Extra</h3>
          <pre>{{ formatJson(selectedLog.extra) }}</pre>
        </div>
      </section>
    </el-dialog>
  </section>
</template>
