<script setup lang="ts">
import { reactive, watch } from 'vue';

import { t } from '@/i18n';

interface SearchOption {
  label: string;
  value: string | number;
}

interface SearchField {
  key: string;
  label: string;
  options?: SearchOption[];
  placeholder?: string;
  type: 'select' | 'text';
}

const props = defineProps<{
  fields: SearchField[];
  modelValue: Record<string, string | number>;
}>();

const emit = defineEmits<{
  reset: [];
  search: [value: Record<string, string | number>];
  'update:modelValue': [value: Record<string, string | number>];
}>();

const formState = reactive<Record<string, string | number>>({ ...props.modelValue });

watch(
  () => props.modelValue,
  (value) => {
    Object.assign(formState, value);
  },
);

function updateField(key: string, value: string | number): void {
  formState[key] = value;
  emit('update:modelValue', { ...formState });
}

function submitSearch(): void {
  emit('search', { ...formState });
}

function resetSearch(): void {
  const nextValue = Object.fromEntries(props.fields.map((field) => [field.key, '']));
  Object.keys(formState).forEach((key) => {
    delete formState[key];
  });
  Object.assign(formState, nextValue);
  emit('update:modelValue', { ...formState });
  emit('reset');
}
</script>

<template>
  <el-form class="search-bar" inline>
    <el-form-item v-for="field in fields" :key="field.key" :label="field.label">
      <el-input
        v-if="field.type === 'text'"
        :model-value="formState[field.key]"
        :placeholder="field.placeholder"
        @update:model-value="updateField(field.key, $event)"
      />
      <el-select
        v-else
        :model-value="formState[field.key]"
        :placeholder="field.placeholder"
        @update:model-value="updateField(field.key, $event)"
      >
        <el-option
          v-for="option in field.options"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
    </el-form-item>

    <el-form-item>
      <el-button type="primary" @click="submitSearch">{{ t('common.query') }}</el-button>
      <el-button @click="resetSearch">{{ t('common.reset') }}</el-button>
    </el-form-item>
  </el-form>
</template>
