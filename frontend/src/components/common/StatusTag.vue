<script setup lang="ts">
import { computed } from 'vue';

const STATUS_MAP: Record<
  string,
  { label: string; type: 'danger' | 'info' | 'primary' | 'success' | 'warning' }
> = {
  approved: { label: '已通过', type: 'success' },
  archived: { label: '已归档', type: 'info' },
  draft: { label: '草稿', type: 'info' },
  pending_review: { label: '待审核', type: 'warning' },
  rejected: { label: '已退回', type: 'danger' },
  submitted: { label: '已提交', type: 'primary' },
};

const props = defineProps<{
  status: string;
}>();

const statusMeta = computed(
  () => STATUS_MAP[props.status] ?? { label: props.status, type: 'info' },
);
</script>

<template>
  <span class="status-tag" :class="`status-tag--${statusMeta.type}`" :data-type="statusMeta.type">
    {{ statusMeta.label }}
  </span>
</template>
