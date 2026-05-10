<script setup lang="ts">
import { computed, reactive, watch } from 'vue';

import type {
  DepartmentCreatePayload,
  DepartmentRead,
  DepartmentUpdatePayload,
} from '@/types/departments';

const props = withDefaults(
  defineProps<{
    department?: DepartmentRead | null;
    modelValue: boolean;
    submitting?: boolean;
  }>(),
  {
    department: null,
    submitting: false,
  },
);

const emit = defineEmits<{
  submit: [payload: DepartmentCreatePayload | DepartmentUpdatePayload];
  'update:modelValue': [value: boolean];
}>();

const form = reactive({
  code: '',
  name: '',
});

const isEditMode = computed(() => Boolean(props.department));
const title = computed(() => (isEditMode.value ? '编辑部门' : '创建部门'));
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});

watch(
  () => [props.modelValue, props.department] as const,
  () => {
    form.code = props.department?.code ?? '';
    form.name = props.department?.name ?? '';
  },
  { immediate: true },
);

function submitForm(): void {
  emit('submit', {
    code: form.code.trim(),
    name: form.name.trim(),
  });
}
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="title" width="480px">
    <el-form class="department-edit-form" label-width="96px">
      <el-form-item label="部门编码">
        <el-input v-model="form.code" autocomplete="off" data-test="department-code-input" />
      </el-form-item>
      <el-form-item label="部门名称">
        <el-input v-model="form.name" autocomplete="off" data-test="department-name-input" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        data-test="department-edit-save"
        :loading="submitting"
        type="primary"
        @click="submitForm"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
