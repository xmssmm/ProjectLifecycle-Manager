<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/useAuthStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const submitting = ref(false);
const form = reactive({
  username: '',
  password: '',
  rememberMe: true,
});

async function submitLogin() {
  submitting.value = true;
  try {
    await authStore.login(form.username.trim(), form.password);
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/';
    await router.replace(redirect);
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 423) {
      ElMessage.error('账号已锁定，请稍后再试');
    } else {
      ElMessage.error('用户名或密码不正确');
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <span class="brand-mark">PM</span>
        <div>
          <h1>项目归档</h1>
          <p>企业项目过程管理与资料归档系统</p>
        </div>
      </div>

      <el-form class="login-form" label-position="top" @submit.prevent="submitLogin">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            autocomplete="username"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            autocomplete="current-password"
            size="large"
            type="password"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-checkbox v-model="form.rememberMe">记住我</el-checkbox>
        <el-button
          class="login-button"
          native-type="submit"
          size="large"
          type="primary"
          :disabled="!form.username || !form.password"
          :loading="submitting"
        >
          登录
        </el-button>
      </el-form>
    </section>
  </main>
</template>
