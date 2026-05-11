<script setup lang="ts">
import { computed } from 'vue';

import { getStatusMeta } from '@/i18n';

const props = defineProps<{
  status: string;
}>();

const statusMeta = computed(() => getStatusMeta(props.status));
</script>

<template>
  <span class="status-tag" :class="`status-tag--${statusMeta.type}`" :data-type="statusMeta.type">
    {{ statusMeta.label }}
  </span>
</template>
