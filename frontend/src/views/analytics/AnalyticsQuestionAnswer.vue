<script setup lang="ts">
import { ChatLineRound } from '@element-plus/icons-vue';
import { computed, ref } from 'vue';

import { useAnalyticsQaStore } from '@/stores/useAnalyticsQaStore';

const store = useAnalyticsQaStore();
const question = ref('');
const examples = ['本部门今年项目数', '平均周期多少', '逾期任务最多的项目'];
const canAsk = computed(() => Boolean(question.value.trim()) && !store.loading);
const visibleColumns = computed(() => {
  if (!store.answer) {
    return [];
  }
  if (store.answer.columns.length > 0) {
    return store.answer.columns.map((column) => column.key);
  }
  return Object.keys(store.answer.rows[0] ?? {});
});

async function ask(): Promise<void> {
  const cleaned = question.value.trim();
  if (!cleaned) {
    return;
  }
  await store.ask(cleaned);
}

async function askExample(example: string): Promise<void> {
  question.value = example;
  await ask();
}
</script>

<template>
  <section class="admin-page analytics-qa-page">
    <div class="admin-page__header">
      <div>
        <h2>指标问答</h2>
        <p>基于白名单数据集生成受控查询，答案引用可见权限范围内的数据。</p>
      </div>
    </div>

    <section class="analytics-qa-page__ask">
      <el-input
        v-model="question"
        data-test="analytics-question"
        placeholder="输入一个指标问题"
        type="textarea"
      />
      <el-button
        data-test="ask-analytics-question"
        :disabled="!canAsk"
        :icon="ChatLineRound"
        :loading="store.loading"
        type="primary"
        @click="ask"
      >
        提问
      </el-button>
    </section>

    <div class="analytics-qa-page__examples">
      <button
        v-for="example in examples"
        :key="example"
        type="button"
        @click="askExample(example)"
      >
        {{ example }}
      </button>
    </div>

    <el-empty v-if="!store.answer" description="暂无问答结果" />

    <template v-else>
      <section class="analytics-qa-page__answer" data-test="analytics-answer">
        <div>
          <h3>{{ store.answer.answer }}</h3>
          <el-tag>{{ store.answer.source }}</el-tag>
        </div>
        <p>
          {{ store.answer.query_config.dataset }} · {{ store.answer.row_count }} 行 ·
          {{ store.answer.chart.type }}
        </p>
      </section>

      <section class="analytics-qa-page__chart" data-test="analytics-chart">
        <strong>{{ store.answer.chart.type }}</strong>
        <span>{{ store.answer.chart.x_field || '-' }} / {{ store.answer.chart.y_field || '-' }}</span>
      </section>

      <div class="analytics-qa-page__table" data-test="analytics-result-table">
        <table>
          <thead>
            <tr>
              <th v-for="column in visibleColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in store.answer.rows" :key="index">
              <td v-for="column in visibleColumns" :key="column">
                {{ row[column] ?? '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.analytics-qa-page {
  display: grid;
  gap: 18px;
}

.analytics-qa-page__ask {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(280px, 1fr) auto;
}

.analytics-qa-page__examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.analytics-qa-page__examples button {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  color: #1f2937;
  background: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.analytics-qa-page__answer,
.analytics-qa-page__chart,
.analytics-qa-page__table {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
}

.analytics-qa-page__answer > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.analytics-qa-page__answer h3 {
  margin: 0;
}

.analytics-qa-page__answer p,
.analytics-qa-page__chart span {
  color: #606266;
  margin: 8px 0 0;
}

.analytics-qa-page__chart {
  display: flex;
  gap: 12px;
}

.analytics-qa-page__table {
  overflow-x: auto;
}

.analytics-qa-page__table table {
  width: 100%;
  border-collapse: collapse;
}

.analytics-qa-page__table th,
.analytics-qa-page__table td {
  padding: 10px;
  border-bottom: 1px solid #eef2f7;
  text-align: left;
}

@media (width <= 900px) {
  .analytics-qa-page__ask {
    grid-template-columns: 1fr;
  }
}
</style>
