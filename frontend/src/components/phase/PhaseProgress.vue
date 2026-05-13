<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { MobileReadOnlyNotice, StatusTag } from '@/components/common';
import { usePermission } from '@/composables/usePermission';
import { usePhaseStore } from '@/stores/usePhaseStore';
import { PHASE_STATUS_LABELS, type PhaseRead, type PhaseStatus } from '@/types/phases';

const props = defineProps<{
  subProjectId: string;
}>();

const emit = defineEmits<{
  promoted: [phase: PhaseRead];
}>();

const phaseStore = usePhaseStore();
const { can } = usePermission();
const errorMessage = ref('');
const orderedPhases = computed(() =>
  [...phaseStore.phases].sort((left, right) => left.phase_no - right.phase_no),
);
const completedCount = computed(
  () => orderedPhases.value.filter((phase) => phase.status === 'completed').length,
);
const progressPercentage = computed(() => {
  if (orderedPhases.value.length === 0) {
    return 0;
  }
  return Math.round((completedCount.value / orderedPhases.value.length) * 100);
});

onMounted(loadPhases);

watch(
  () => props.subProjectId,
  async () => {
    await loadPhases();
  },
);

async function loadPhases(): Promise<void> {
  errorMessage.value = '';
  await phaseStore.fetchPhases(props.subProjectId);
}

async function promote(phase: PhaseRead): Promise<void> {
  errorMessage.value = '';
  try {
    const result = await phaseStore.promotePhase(phase.id);
    emit('promoted', result.phase);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  }
}

function canPromote(phase: PhaseRead): boolean {
  return phase.status === 'in_progress' && can('phase.promote');
}

function statusLabel(status: PhaseStatus): string {
  return PHASE_STATUS_LABELS[status];
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : '-';
}

function extractErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'message' in error.response.data
  ) {
    return String(error.response.data.message);
  }
  return '环节推进失败';
}
</script>

<template>
  <section class="project-detail-band phase-progress">
    <div class="project-detail-band__header">
      <div>
        <h3>环节进度</h3>
        <span>{{ completedCount }} / {{ orderedPhases.length }} 已完成</span>
      </div>
      <el-progress class="phase-progress__bar" :percentage="progressPercentage" />
    </div>

    <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
    <p class="phase-progress__hint">
      需要查看缺失材料时，请在下方环节材料区处理并推进。
    </p>
    <MobileReadOnlyNotice
      data-test="mobile-read-only-phase"
      message="移动端仅支持查看环节进度，请切换到 PC 端推进环节。"
    />

    <div v-if="orderedPhases.length > 0" class="phase-progress__list">
      <article
        v-for="phase in orderedPhases"
        :key="phase.id"
        class="phase-progress__item"
        :class="`phase-progress__item--${phase.status}`"
        data-test="phase-item"
      >
        <div class="phase-progress__badge">{{ phase.phase_no }}</div>
        <div class="phase-progress__body">
          <div class="phase-progress__title">
            <h4>{{ phase.name }}</h4>
            <StatusTag :status="phase.status" />
            <span data-test="phase-status-code" class="phase-progress__code">
              {{ phase.status }}
            </span>
            <span class="sr-only">{{ statusLabel(phase.status) }}</span>
          </div>
          <p>{{ phase.code }} · 进入 {{ formatDate(phase.enter_at) }}</p>
          <p>完成 {{ formatDate(phase.finish_at) }}</p>
        </div>
        <el-button
          v-if="canPromote(phase)"
          class="desktop-only-action"
          :data-test="`promote-${phase.id}`"
          :loading="phaseStore.promotingId === phase.id"
          size="small"
          type="primary"
          @click="promote(phase)"
        >
          推进
        </el-button>
      </article>
    </div>

    <el-empty v-else-if="!phaseStore.loading" description="暂无环节" />
  </section>
</template>
