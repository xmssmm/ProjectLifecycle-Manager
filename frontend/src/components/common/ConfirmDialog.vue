<script setup lang="ts">
import { computed } from 'vue';

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
    cancelText: '取消',
    confirmDataTest: undefined,
    confirmText: '确认',
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
      <el-button :data-test="cancelDataTest" @click="closeDialog">{{ cancelText }}</el-button>
      <el-button :data-test="confirmDataTest" :type="type" @click="confirmAction">
        {{ confirmText }}
      </el-button>
    </template>
  </el-dialog>
</template>
