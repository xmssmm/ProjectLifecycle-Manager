<script setup lang="ts">
import { onMounted } from 'vue';

import { useAuthStore } from '@/stores/useAuthStore';
import { useUserStore } from '@/stores/useUserStore';
import { formatUserDateTime } from '@/utils/timezone';

const authStore = useAuthStore();
const userStore = useUserStore();

onMounted(async () => {
  await userStore.fetchSubProjectHandovers({ page: 1, pageSize: 20 });
});

function formatDate(value: string): string {
  return formatUserDateTime(value, authStore.user?.timezone);
}
</script>

<template>
  <section class="admin-page project-page">
    <div class="admin-page__header">
      <div>
        <h2>转交历史</h2>
        <p>按子项目、原负责人、新负责人回溯负责人变更记录。</p>
      </div>
      <router-link :to="{ name: 'admin-handover' }">
        <el-button>返回转交</el-button>
      </router-link>
    </div>

    <section class="project-detail-band">
      <div class="project-member-table">
        <table>
          <thead>
            <tr>
              <th>记录 ID</th>
              <th>子项目</th>
              <th>原负责人</th>
              <th>新负责人</th>
              <th>操作人</th>
              <th>原因</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="handover in userStore.handoverHistory" :key="handover.id">
              <td>{{ handover.id }}</td>
              <td>{{ handover.sub_project_id }}</td>
              <td>{{ handover.from_user_id }}</td>
              <td>{{ handover.to_user_id }}</td>
              <td>{{ handover.operator_id }}</td>
              <td>{{ handover.reason }}</td>
              <td>{{ formatDate(handover.operated_at) }}</td>
            </tr>
          </tbody>
        </table>
        <el-empty v-if="!userStore.handoverHistory.length" description="暂无转交历史" />
      </div>
    </section>
  </section>
</template>
