<script setup lang="ts">
import { Lock, OfficeBuilding, User } from '@element-plus/icons-vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { completeOAuthCallback, listOAuthProviders, startOAuthLogin } from '@/api/oauth';
import { useAuthStore } from '@/stores/useAuthStore';
import type { OAuthProviderRead } from '@/types/oauth';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const submitting = ref(false);
const oauthCallbackLoading = ref(false);
const oauthProviders = ref<OAuthProviderRead[]>([]);
const oauthSubmittingProvider = ref<string | null>(null);
const form = reactive({
  username: '',
  password: '',
  rememberMe: true,
});

onMounted(async () => {
  await completeOAuthCallbackIfPresent();
  await loadOAuthProviders();
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

async function loadOAuthProviders(): Promise<void> {
  try {
    oauthProviders.value = await listOAuthProviders();
  } catch {
    oauthProviders.value = [];
  }
}

async function completeOAuthCallbackIfPresent(): Promise<void> {
  const provider = routeQueryString('oauth_provider');
  const code = routeQueryString('code');
  const state = routeQueryString('state');
  if (!provider || !code || !state) {
    return;
  }

  oauthCallbackLoading.value = true;
  try {
    const tokens = await completeOAuthCallback({ provider, code, state });
    await authStore.applyTokenPair(tokens);
    const redirect = routeQueryString('redirect') ?? '/';
    await router.replace(redirect);
  } catch {
    ElMessage.error('企业账号登录失败，请重新尝试');
  } finally {
    oauthCallbackLoading.value = false;
  }
}

async function startProviderLogin(provider: string): Promise<void> {
  oauthSubmittingProvider.value = provider;
  try {
    const started = await startOAuthLogin(provider);
    globalThis.location.assign(started.authorization_url);
  } catch {
    ElMessage.error('企业账号登录暂不可用');
  } finally {
    oauthSubmittingProvider.value = null;
  }
}

function routeQueryString(key: string): string | null {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : null;
  }
  return typeof value === 'string' && value ? value : null;
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

      <template v-if="oauthProviders.length > 0">
        <el-divider>企业账号登录</el-divider>
        <div class="oauth-login-list">
          <el-button
            v-for="provider in oauthProviders"
            :key="provider.provider"
            class="oauth-login-button"
            :data-test="`oauth-login-${provider.provider}`"
            :icon="OfficeBuilding"
            :loading="oauthSubmittingProvider === provider.provider"
            size="large"
            @click="startProviderLogin(provider.provider)"
          >
            {{ provider.label }}
          </el-button>
        </div>
      </template>

      <p v-if="oauthCallbackLoading" class="oauth-callback-status">正在完成企业账号登录</p>
    </section>
  </main>
</template>
