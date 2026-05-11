<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue';
import { computed, onMounted, ref, watch } from 'vue';

import { useProjectBenchmarkStore } from '@/stores/useProjectBenchmarkStore';
import type { ProjectBenchmarkMetric } from '@/types/projectBenchmarks';

const props = defineProps<{
  projectId?: string;
}>();

const store = useProjectBenchmarkStore();
const selectedProjectId = ref(props.projectId ?? '');
const highlightedKeys = ['cycle_days', 'budget_variance_percent', 'task_overdue_rate'];
const highlightedMetrics = computed(() =>
  highlightedKeys
    .map((key) => store.benchmark?.metrics.find((metric) => metric.key === key))
    .filter((metric): metric is ProjectBenchmarkMetric => Boolean(metric)),
);
const phaseMetric = computed(() =>
  store.benchmark?.metrics.find((metric) => metric.key === 'phase_stay_days'),
);
const isInsufficient = computed(() => store.benchmark?.status === 'insufficient_sample');
const canRun = computed(() => Boolean(selectedProjectId.value.trim()) && !store.loading);

onMounted(() => {
  if (selectedProjectId.value) {
    void runBenchmark();
  }
});

watch(
  () => props.projectId,
  (projectId) => {
    selectedProjectId.value = projectId ?? selectedProjectId.value;
  },
);

async function runBenchmark(): Promise<void> {
  if (!selectedProjectId.value.trim()) {
    return;
  }
  await store.fetchBenchmark(selectedProjectId.value.trim());
}

function formatMetric(value: number | null, unit: string): string {
  if (value === null) {
    return '-';
  }
  return `${value.toFixed(2)} ${unit}`;
}
</script>

<template>
  <section class="admin-page benchmark-page">
    <div class="admin-page__header">
      <div>
        <h2>跨项目对标分析</h2>
        <p>按可见历史样本比较周期、预算偏差、环节停留和任务逾期。</p>
      </div>
      <div class="benchmark-page__query">
        <el-input
          v-model="selectedProjectId"
          data-test="benchmark-project-id"
          placeholder="主项目 ID"
        />
        <el-button
          data-test="run-benchmark"
          :disabled="!canRun"
          :icon="Refresh"
          :loading="store.loading"
          type="primary"
          @click="runBenchmark"
        >
          分析
        </el-button>
      </div>
    </div>

    <el-skeleton :loading="store.loading && !store.benchmark" animated>
      <template #default>
        <el-empty v-if="!store.benchmark" description="请选择项目" />
        <template v-else>
          <el-alert
            v-if="isInsufficient"
            :closable="false"
            :title="`样本不足，仅找到 ${store.benchmark.sample_count} 个可对标项目`"
            type="warning"
          />

          <section class="benchmark-page__cards">
            <article
              v-for="metric in highlightedMetrics"
              :key="metric.key"
              class="benchmark-card"
              :data-test="`benchmark-${metric.key}`"
            >
              <div>
                <h3>{{ metric.label }}</h3>
                <p>当前 {{ formatMetric(metric.current_value, metric.unit) }}</p>
              </div>
              <dl>
                <div>
                  <dt>P50</dt>
                  <dd>{{ formatMetric(metric.p50, metric.unit) }}</dd>
                </div>
                <div>
                  <dt>P90</dt>
                  <dd>{{ formatMetric(metric.p90, metric.unit) }}</dd>
                </div>
                <div>
                  <dt>均值</dt>
                  <dd>{{ formatMetric(metric.average, metric.unit) }}</dd>
                </div>
              </dl>
            </article>
          </section>

          <section v-if="phaseMetric" class="benchmark-page__phase">
            <h3>{{ phaseMetric.label }}</h3>
            <p>
              当前 {{ formatMetric(phaseMetric.current_value, phaseMetric.unit) }}，P50
              {{ formatMetric(phaseMetric.p50, phaseMetric.unit) }}，P90
              {{ formatMetric(phaseMetric.p90, phaseMetric.unit) }}
            </p>
          </section>
        </template>
      </template>
    </el-skeleton>
  </section>
</template>

<style scoped>
.benchmark-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.benchmark-page__query,
.benchmark-page__cards {
  display: grid;
  gap: 12px;
}

.benchmark-page__query {
  grid-template-columns: minmax(260px, 360px) auto;
}

.benchmark-page__cards {
  grid-template-columns: repeat(3, minmax(180px, 1fr));
}

.benchmark-card,
.benchmark-page__phase {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 18px;
}

.benchmark-card h3,
.benchmark-page__phase h3 {
  margin: 0 0 6px;
}

.benchmark-card p,
.benchmark-page__phase p {
  color: #606266;
  margin: 0;
}

.benchmark-card dl {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, 1fr);
  margin: 16px 0 0;
}

.benchmark-card dt {
  color: #909399;
  font-size: 12px;
}

.benchmark-card dd {
  font-weight: 700;
  margin: 4px 0 0;
}

@media (width <= 900px) {
  .benchmark-page__query,
  .benchmark-page__cards {
    grid-template-columns: 1fr;
  }
}
</style>
