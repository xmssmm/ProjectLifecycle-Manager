<script setup lang="ts">
defineProps<{
  message: string;
}>();
</script>

<template>
  <p class="mobile-read-only-notice">
    {{ message }}
  </p>
</template>
