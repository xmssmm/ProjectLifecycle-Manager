<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    allowedRoles?: string[];
    currentRole?: string | null;
    ownedResourceIds?: string[];
    permission: string;
    resourceId?: string;
  }>(),
  {
    allowedRoles: () => [],
    currentRole: null,
    ownedResourceIds: () => [],
    resourceId: undefined,
  },
);

const canAccess = computed(() => {
  if (!props.permission || !props.currentRole) {
    return false;
  }

  if (props.currentRole === 'admin' || props.allowedRoles.includes(props.currentRole)) {
    return true;
  }

  return Boolean(props.resourceId && props.ownedResourceIds.includes(props.resourceId));
});
</script>

<template>
  <slot v-if="canAccess" />
  <slot v-else name="fallback" />
</template>
