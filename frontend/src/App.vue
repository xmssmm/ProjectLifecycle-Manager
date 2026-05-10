<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import AppLayout from '@/components/layout/AppLayout.vue';

const route = useRoute();
const usesAppShell = computed(() => route.meta.layout !== 'auth');
</script>

<template>
  <AppLayout v-if="usesAppShell" />
  <router-view v-else />
</template>
