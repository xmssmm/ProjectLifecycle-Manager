<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { useMainProjectStore } from '@/stores/useMainProjectStore';
import type { MainProjectRead, ProjectStatus } from '@/types/projects';

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    includeStatuses?: ProjectStatus[];
    modelValue: string;
    placeholder?: string;
  }>(),
  {
    disabled: false,
    includeStatuses: () => ['not_started', 'in_progress'],
    placeholder: '请选择已审核主项目',
  },
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const mainProjectStore = useMainProjectStore();
const selectedValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
});

const selectableProjects = computed<MainProjectRead[]>(() =>
  mainProjectStore.projects.filter((project) => props.includeStatuses.includes(project.status)),
);

onMounted(async () => {
  await mainProjectStore.fetchMainProjects({ page: 1, pageSize: 100 });
});
</script>

<template>
  <el-select
    v-model="selectedValue"
    data-test="main-project-select"
    :disabled="disabled"
    filterable
    :loading="mainProjectStore.loading"
    :placeholder="placeholder"
  >
    <el-option
      v-for="project in selectableProjects"
      :key="project.id"
      :label="`${project.project_no} · ${project.name}`"
      :value="project.id"
    />
  </el-select>
</template>
