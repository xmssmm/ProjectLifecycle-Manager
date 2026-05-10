<script setup lang="ts">
import { computed } from 'vue';

const STATUS_MAP: Record<
  string,
  { label: string; type: 'danger' | 'info' | 'primary' | 'success' | 'warning' }
> = {
  approved: { label: '已通过', type: 'success' },
  archived: { label: '已归档', type: 'info' },
  active: { label: '启用', type: 'success' },
  closed: { label: '已结项', type: 'info' },
  completed: { label: '已完成', type: 'success' },
  disabled: { label: '停用', type: 'info' },
  draft: { label: '草稿', type: 'info' },
  in_progress: { label: '进行中', type: 'primary' },
  not_started: { label: '未开始', type: 'info' },
  pending_review: { label: '待审核', type: 'warning' },
  password_reset_required: { label: '需改密', type: 'warning' },
  rejected: { label: '已退回', type: 'danger' },
  reviewing: { label: '审核中', type: 'primary' },
  submitted: { label: '已提交', type: 'primary' },
  terminated: { label: '已中止', type: 'danger' },
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
