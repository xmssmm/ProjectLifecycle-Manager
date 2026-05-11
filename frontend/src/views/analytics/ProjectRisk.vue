<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue';
import { computed, onMounted, ref, watch } from 'vue';

import { useProjectRiskStore } from '@/stores/useProjectRiskStore';
import type { ProjectRiskLevel } from '@/types/projectRisk';

const props = defineProps<{
  projectId?: string;
}>();

const store = useProjectRiskStore();
const selectedProjectId = ref(props.projectId ?? '');
const canRun = computed(() => Boolean(selectedProjectId.value.trim()) && !store.loading);
const progressStatus = computed(() => {
  const level = store.risk?.level;
  if (level === 'critical' || level === 'high') {
    return 'exception';
  }
  if (level === 'medium') {
    return 'warning';
  }
  return 'success';
});

onMounted(() => {
  if (selectedProjectId.value) {
    void runRisk();
  }
});

watch(
  () => props.projectId,
  (projectId) => {
    selectedProjectId.value = projectId ?? selectedProjectId.value;
  },
);

async function runRisk(): Promise<void> {
  if (!selectedProjectId.value.trim()) {
    return;
  }
  await store.fetchRisk(selectedProjectId.value.trim());
}

function levelTagType(level: ProjectRiskLevel): 'danger' | 'info' | 'success' | 'warning' {
  if (level === 'critical' || level === 'high') {
    return 'danger';
  }
  if (level === 'medium') {
    return 'warning';
  }
  return 'success';
}
</script>

<template>
  <section class="admin-page risk-page">
    <div class="admin-page__header">
      <div>
        <h2>项目风险评分</h2>
        <p>根据延期、预算偏差、逾期任务和对标偏差生成确定性风险评分。</p>
      </div>
      <div class="risk-page__query">
        <el-input v-model="selectedProjectId" data-test="risk-project-id" placeholder="主项目 ID" />
        <el-button
          data-test="run-risk"
          :disabled="!canRun"
          :icon="Refresh"
          :loading="store.loading"
          type="primary"
          @click="runRisk"
        >
          评分
        </el-button>
      </div>
    </div>

    <el-skeleton :loading="store.loading && !store.risk" animated>
      <template #default>
        <el-empty v-if="!store.risk" description="请选择项目" />
        <template v-else>
          <section class="risk-page__score">
            <div>
              <span class="risk-page__score-value">{{ store.risk.score }}</span>
              <el-tag :type="levelTagType(store.risk.level)">{{ store.risk.level }}</el-tag>
            </div>
            <el-progress :percentage="store.risk.score" :status="progressStatus" />
          </section>

          <section class="risk-page__summary">
            <h3>解释摘要</h3>
            <p>{{ store.risk.summary.text }}</p>
            <el-tag>{{ store.risk.summary.source }}</el-tag>
          </section>

          <section class="risk-page__grid">
            <article class="risk-panel">
              <h3>风险原因</h3>
              <ul>
                <li v-for="reason in store.risk.reasons" :key="reason.code">
                  <strong>{{ reason.message }}</strong>
                  <span>{{ reason.score }} 分</span>
                </li>
              </ul>
            </article>
            <article class="risk-panel">
              <h3>建议动作</h3>
              <ul>
                <li v-for="action in store.risk.actions" :key="action">{{ action }}</li>
              </ul>
            </article>
          </section>
        </template>
      </template>
    </el-skeleton>
  </section>
</template>

<style scoped>
.risk-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.risk-page__query {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(260px, 360px) auto;
}

.risk-page__score,
.risk-page__summary,
.risk-panel {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 18px;
}

.risk-page__score {
  display: grid;
  gap: 14px;
}

.risk-page__score > div {
  align-items: center;
  display: flex;
  gap: 12px;
}

.risk-page__score-value {
  font-size: 42px;
  font-weight: 800;
}

.risk-page__summary h3,
.risk-panel h3 {
  margin: 0 0 10px;
}

.risk-page__summary p {
  color: #606266;
  margin: 0 0 12px;
}

.risk-page__grid {
  display: grid;
  gap: 18px;
  grid-template-columns: 1fr 1fr;
}

.risk-panel ul {
  display: grid;
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.risk-panel li {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

@media (width <= 900px) {
  .risk-page__query,
  .risk-page__grid {
    grid-template-columns: 1fr;
  }
}
</style>
