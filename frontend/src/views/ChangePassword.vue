<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/useAuthStore';
import { useProfileStore } from '@/stores/useProfileStore';

const authStore = useAuthStore();
const profileStore = useProfileStore();
const router = useRouter();
const errorMessage = ref('');

const form = reactive({
  confirmPassword: '',
  newPassword: '',
  oldPassword: '',
});

const isForcedReset = computed(() => authStore.user?.status === 'password_reset_required');

function validatePassword(): string {
  if (form.newPassword !== form.confirmPassword) {
    return '两次输入的新密码不一致';
  }
  if (form.newPassword.length < 8) {
    return '新密码至少需要 8 位';
  }
  if (!/[A-Z]/.test(form.newPassword)) {
    return '新密码需要包含大写字母';
  }
  if (!/[a-z]/.test(form.newPassword)) {
    return '新密码需要包含小写字母';
  }
  if (!/\d/.test(form.newPassword)) {
    return '新密码需要包含数字';
  }
  if (!/[^A-Za-z0-9]/.test(form.newPassword)) {
    return '新密码需要包含特殊字符';
  }
  return '';
}

async function submitPassword(): Promise<void> {
  errorMessage.value = validatePassword();
  if (errorMessage.value) {
    return;
  }

  try {
    await profileStore.changePassword({
      new_password: form.newPassword,
      old_password: form.oldPassword,
    });
    ElMessage.success('密码已修改，请重新登录');
    authStore.clearSession();
    await router.replace({ name: 'login' });
  } catch {
    errorMessage.value = '修改密码失败，请检查旧密码或新密码强度';
  }
}
</script>

<template>
  <section class="admin-page profile-page">
    <div class="admin-page__header">
      <div>
        <h2>修改密码</h2>
        <p>修改后需要重新登录。</p>
      </div>
    </div>

    <div class="admin-page__table profile-panel">
      <el-alert
        v-if="isForcedReset"
        class="profile-alert"
        show-icon
        title="管理员已重置你的密码，请先设置新密码。"
        type="warning"
      />
      <el-alert v-if="errorMessage" class="profile-alert" :title="errorMessage" type="error" />

      <el-form class="profile-form" label-width="112px">
        <el-form-item label="旧密码">
          <el-input
            v-model="form.oldPassword"
            autocomplete="current-password"
            data-test="old-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="form.newPassword"
            autocomplete="new-password"
            data-test="new-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="form.confirmPassword"
            autocomplete="new-password"
            data-test="confirm-password"
            show-password
            type="password"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            data-test="password-save"
            :loading="profileStore.saving"
            type="primary"
            @click="submitPassword"
          >
            保存新密码
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </section>
</template>
