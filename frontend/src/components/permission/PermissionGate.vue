<script setup lang="ts">
import { computed } from 'vue';

import { usePermission, type PermissionCode } from '@/composables/usePermission';

const props = withDefaults(
  defineProps<{
    ownedResourceIds?: string[];
    permission: PermissionCode;
    resourceId?: string;
  }>(),
  {
    ownedResourceIds: () => [],
    resourceId: undefined,
  },
);

const { can } = usePermission();
const canAccess = computed(() =>
  can(props.permission, {
    ownedResourceIds: props.ownedResourceIds,
    resourceId: props.resourceId,
  }),
);
</script>

<template>
  <slot v-if="canAccess" />
  <slot v-else name="fallback" />
</template>
