<script setup lang="ts">
import { computed, reactive, watch } from 'vue';

import type { UserCreatePayload, UserRead, UserUpdatePayload } from '@/types/users';
import { ROLE_LABELS } from '@/types/users';
import type { UserRole } from '@/stores/useAuthStore';

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    submitting?: boolean;
    user?: UserRead | null;
  }>(),
  {
    submitting: false,
    user: null,
  },
);

const emit = defineEmits<{
  submit: [payload: UserCreatePayload | UserUpdatePayload];
  'update:modelValue': [value: boolean];
}>();

const roleOptions = Object.entries(ROLE_LABELS).map(([value, label]) => ({
  label,
  value: value as UserRole,
}));

const form = reactive({
  deptId: '',
  email: '',
  password: '',
  role: 'proj_member' as UserRole,
  ssoRequired: false,
  username: '',
});

const isEditMode = computed(() => Boolean(props.user));
const title = computed(() => (isEditMode.value ? '编辑用户' : '创建用户'));
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});

watch(
  () => [props.modelValue, props.user] as const,
  () => {
    form.deptId = props.user?.dept_id ?? '';
    form.email = props.user?.email ?? '';
    form.password = '';
    form.role = props.user?.role ?? 'proj_member';
    form.ssoRequired = props.user?.sso_required ?? false;
    form.username = props.user?.username ?? '';
  },
  { immediate: true },
);

function normalizeNullable(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function submitForm(): void {
  const basePayload = {
    dept_id: normalizeNullable(form.deptId),
    email: normalizeNullable(form.email),
    role: form.role,
    sso_required: form.ssoRequired,
    username: form.username.trim(),
  };

  if (isEditMode.value) {
    emit('submit', basePayload);
    return;
  }

  emit('submit', {
    ...basePayload,
    password: form.password,
  });
}
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="title" width="520px">
    <el-form class="user-edit-form" label-width="96px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" autocomplete="off" data-test="user-name-input" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" autocomplete="off" data-test="user-email-input" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option
            v-for="option in roleOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="部门 ID">
        <el-input
          v-model="form.deptId"
          autocomplete="off"
          data-test="user-dept-input"
          placeholder="可留空"
        />
      </el-form-item>
      <el-form-item label="登录策略">
        <el-switch
          v-model="form.ssoRequired"
          active-text="仅 SSO"
          data-test="user-sso-required"
          inactive-text="本地+SSO"
        />
      </el-form-item>
      <el-form-item v-if="!isEditMode" label="初始密码">
        <el-input
          v-model="form.password"
          autocomplete="new-password"
          data-test="user-password-input"
          show-password
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        data-test="user-edit-save"
        :loading="submitting"
        type="primary"
        @click="submitForm"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
