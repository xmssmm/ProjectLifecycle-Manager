<script setup lang="ts">
import { computed } from 'vue';

import { t } from '@/i18n';

const props = withDefaults(
  defineProps<{
    cancelDataTest?: string;
    cancelText?: string;
    confirmDataTest?: string;
    confirmText?: string;
    message: string;
    modelValue: boolean;
    title: string;
    type?: 'danger' | 'primary' | 'warning';
  }>(),
  {
    cancelDataTest: undefined,
    cancelText: undefined,
    confirmDataTest: undefined,
    confirmText: undefined,
    type: 'primary',
  },
);

const emit = defineEmits<{
  cancel: [];
  confirm: [];
  'update:modelValue': [value: boolean];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});
const cancelLabel = computed(() => props.cancelText ?? t('common.cancel'));
const confirmLabel = computed(() => props.confirmText ?? t('common.confirm'));

function closeDialog(): void {
  emit('cancel');
  visible.value = false;
}

function confirmAction(): void {
  emit('confirm');
  visible.value = false;
}
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="420px">
    <p class="confirm-dialog__message">{{ message }}</p>
    <slot />
    <template #footer>
      <el-button :data-test="cancelDataTest" @click="closeDialog">{{ cancelLabel }}</el-button>
      <el-button :data-test="confirmDataTest" :type="type" @click="confirmAction">
        {{ confirmLabel }}
      </el-button>
    </template>
  </el-dialog>
</template>
