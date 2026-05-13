<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { useDepartmentStore } from '@/stores/useDepartmentStore';

const props = defineProps<{
  disabled?: boolean;
  modelValue: string;
  placeholder?: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const departmentStore = useDepartmentStore();
const selectedValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
});

onMounted(async () => {
  await departmentStore.fetchDepartments();
});
</script>

<template>
  <el-select
    v-model="selectedValue"
    data-test="department-select"
    :disabled="disabled"
    filterable
    :loading="departmentStore.loading"
    :placeholder="placeholder ?? '请选择责任部门'"
  >
    <el-option
      v-for="department in departmentStore.departments"
      :key="department.id"
      :label="`${department.name}（${department.code}）`"
      :value="department.id"
    />
  </el-select>
</template>
