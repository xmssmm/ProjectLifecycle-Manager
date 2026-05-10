<script setup lang="ts">
import * as echarts from 'echarts';
import type { ECharts, EChartsOption } from 'echarts';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { DashboardChartPoint } from '@/types/dashboard';

const props = withDefaults(
  defineProps<{
    points: DashboardChartPoint[];
    title: string;
    type?: 'bar' | 'pie';
  }>(),
  {
    type: 'bar',
  },
);

const chartRoot = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;

onMounted(() => {
  renderChart();
  window.addEventListener('resize', resizeChart);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart);
  chart?.dispose();
  chart = null;
});

watch(
  () => props.points,
  () => renderChart(),
  { deep: true },
);

function renderChart(): void {
  if (!chartRoot.value) {
    return;
  }
  chart ??= echarts.init(chartRoot.value);
  chart.setOption(buildOption(), true);
}

function resizeChart(): void {
  chart?.resize();
}

function buildOption(): EChartsOption {
  const points = props.points.map((point) => ({
    name: point.label,
    value: normalizeValue(point.value),
  }));

  if (props.type === 'pie') {
    return {
      color: ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2'],
      series: [
        {
          data: points,
          radius: ['42%', '70%'],
          type: 'pie',
        },
      ],
      tooltip: { trigger: 'item' },
    };
  }

  return {
    color: ['#2563eb'],
    grid: { bottom: 28, left: 36, right: 16, top: 20 },
    series: [{ data: points.map((point) => point.value), type: 'bar' }],
    tooltip: { trigger: 'axis' },
    xAxis: {
      axisLabel: { color: '#667085' },
      data: points.map((point) => point.name),
      type: 'category',
    },
    yAxis: {
      axisLabel: { color: '#667085' },
      splitLine: { lineStyle: { color: '#e5e9f0' } },
      type: 'value',
    },
  };
}

function normalizeValue(value: number | string): number {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : 0;
}
</script>

<template>
  <div ref="chartRoot" class="dashboard-chart" :aria-label="title" role="img" />
</template>
