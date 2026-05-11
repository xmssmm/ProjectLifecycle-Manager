<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import type { CustomReportChartType, ReportDatasetFieldRead } from '@/types/customReports';

const props = defineProps<{
  chartType: CustomReportChartType;
  columns: ReportDatasetFieldRead[];
  rows: Record<string, unknown>[];
}>();

const chartElement = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;

const tableRows = computed(() => props.rows);
const primaryColumn = computed(() => props.columns[0]?.key ?? '');
const valueColumn = computed(() => props.columns[1]?.key ?? props.columns[0]?.key ?? '');
const showChart = computed(() => props.chartType !== 'table' && props.rows.length > 0);

watch(
  () => [props.chartType, props.columns, props.rows] as const,
  async () => {
    await renderChart();
  },
  { deep: true, immediate: true },
);

onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});

async function renderChart(): Promise<void> {
  await nextTick();
  if (!showChart.value || !chartElement.value) {
    chart?.dispose();
    chart = null;
    return;
  }
  chart = chart ?? echarts.init(chartElement.value);
  chart.setOption({
    grid: { bottom: 32, left: 48, right: 16, top: 24 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      data: props.rows.map((row) => String(row[primaryColumn.value] ?? '')),
      type: 'category',
    },
    yAxis: { type: 'value' },
    series: [
      {
        data: props.rows.map((row) => Number(row[valueColumn.value] ?? 0)),
        smooth: props.chartType === 'line',
        type: props.chartType,
      },
    ],
  });
}
</script>

<template>
  <div class="report-preview">
    <div v-if="showChart" ref="chartElement" class="report-preview__chart" />
    <el-table v-else :data="tableRows" size="small">
      <el-table-column
        v-for="column in columns"
        :key="column.key"
        :label="column.label"
        :prop="column.key"
        min-width="140"
      />
    </el-table>
  </div>
</template>

<style scoped>
.report-preview {
  min-height: 220px;
}

.report-preview__chart {
  min-height: 260px;
}
</style>
