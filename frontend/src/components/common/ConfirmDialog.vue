<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    cancelText?: string;
    confirmText?: string;
    message: string;
    modelValue: boolean;
    title: string;
    type?: 'danger' | 'primary' | 'warning';
  }>(),
  {
    cancelText: '取消',
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
      <el-button @click="closeDialog">{{ cancelText }}</el-button>
      <el-button :type="type" @click="confirmAction">
        {{ confirmText }}
      </el-button>
    </template>
  </el-dialog>
</template>
