<script setup lang="ts">
import * as echarts from 'echarts';
import type { ECharts, EChartsOption } from 'echarts';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { StatusTag } from '@/components/common';
import type { ProjectProgressFunnelItem, ProjectProgressFunnelRead } from '@/types/projects';

const props = defineProps<{
  funnel: ProjectProgressFunnelRead | null;
  loading: boolean;
}>();

const chartRoot = ref<HTMLDivElement | null>(null);
const selectedPhaseNo = ref<number | null>(null);
let chart: ECharts | null = null;

const items = computed(() => [...(props.funnel?.items ?? [])].sort(comparePhaseNo));
const selectedItem = computed(() => {
  if (items.value.length === 0) {
    return null;
  }
  return (
    items.value.find((item) => item.phase_no === selectedPhaseNo.value) ??
    items.value.find((item) => item.sub_project_count > 0) ??
    items.value[0]
  );
});

onMounted(() => {
  renderChart();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  chart?.dispose();
  chart = null;
});

watch(
  items,
  () => {
    if (!items.value.some((item) => item.phase_no === selectedPhaseNo.value)) {
      selectedPhaseNo.value = selectedItem.value?.phase_no ?? null;
    }
    renderChart();
  },
  { deep: true, immediate: true },
);

function renderChart(): void {
  if (!chartRoot.value || items.value.length === 0) {
    return;
  }
  chart ??= echarts.init(chartRoot.value);
  chart.setOption(buildOption(), true);
  chart.off('click');
  chart.on('click', (params) => {
    const phaseNo = Number((params.data as { phase_no?: number } | undefined)?.phase_no);
    if (Number.isFinite(phaseNo)) {
      selectedPhaseNo.value = phaseNo;
    }
  });
}

function buildOption(): EChartsOption {
  return {
    color: ['#2563eb', '#16a34a', '#0891b2', '#f59e0b', '#7c3aed', '#dc2626'],
    series: [
      {
        data: items.value.map((item) => ({
          name: item.name,
          phase_no: item.phase_no,
          value: item.sub_project_count,
        })),
        gap: 4,
        label: { formatter: '{b}: {c}' },
        sort: 'none',
        type: 'funnel',
      },
    ],
    tooltip: { trigger: 'item' },
  };
}

function selectPhase(item: ProjectProgressFunnelItem): void {
  selectedPhaseNo.value = item.phase_no;
}

function handleResize(): void {
  chart?.resize();
}

function comparePhaseNo(left: ProjectProgressFunnelItem, right: ProjectProgressFunnelItem): number {
  return left.phase_no - right.phase_no;
}
</script>

<template>
  <section class="project-detail-band progress-funnel">
    <div class="project-detail-band__header">
      <div>
        <h3>项目进度漏斗</h3>
        <span>{{ funnel?.total_sub_projects ?? 0 }} 个子项目</span>
      </div>
    </div>

    <el-skeleton v-if="loading && !funnel" animated />

    <template v-else-if="items.length > 0">
      <div
        ref="chartRoot"
        aria-label="项目进度漏斗"
        class="progress-funnel__chart"
        data-test="progress-funnel-chart"
        role="img"
      />

      <div class="progress-funnel__phases">
        <button
          v-for="item in items"
          :key="item.phase_no"
          class="progress-funnel__phase"
          :class="{ 'progress-funnel__phase--active': item.phase_no === selectedItem?.phase_no }"
          :data-test="`progress-funnel-phase-${item.phase_no}`"
          type="button"
          @click="selectPhase(item)"
        >
          <span>{{ item.phase_no }}. {{ item.name }}</span>
          <strong>{{ item.sub_project_count }}</strong>
        </button>
      </div>

      <div class="progress-funnel__drill">
        <div class="project-detail-band__header">
          <h3>{{ selectedItem?.name ?? '环节' }}子项目</h3>
          <span>{{ selectedItem?.sub_project_count ?? 0 }} 个</span>
        </div>
        <div
          v-if="selectedItem && selectedItem.sub_projects.length > 0"
          class="progress-funnel__drill-list"
          data-test="progress-funnel-drill-list"
        >
          <router-link
            v-for="subProject in selectedItem.sub_projects"
            :key="subProject.id"
            class="progress-funnel__drill-item"
            :to="{ name: 'sub-project-detail', params: { id: subProject.id } }"
          >
            <div>
              <strong>{{ subProject.name }}</strong>
              <p>{{ subProject.project_no }}</p>
            </div>
            <StatusTag :status="subProject.status" />
          </router-link>
        </div>
        <el-empty v-else description="该环节暂无子项目" />
      </div>
    </template>

    <el-empty v-else description="暂无进度数据" />
  </section>
</template>
