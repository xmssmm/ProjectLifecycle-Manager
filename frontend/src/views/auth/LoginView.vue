<script setup lang="ts">
import { Lock, OfficeBuilding, User } from '@element-plus/icons-vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { completeOAuthCallback, listOAuthProviders, startOAuthLogin } from '@/api/oauth';
import { t } from '@/i18n';
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
      ElMessage.error(t('auth.errors.locked'));
    } else {
      ElMessage.error(t('auth.errors.passwordInvalid'));
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
    ElMessage.error(t('auth.errors.oauthFailed'));
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
    ElMessage.error(t('auth.errors.oauthUnavailable'));
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
          <h1>{{ t('app.brand') }}</h1>
          <p>{{ t('app.title') }}</p>
        </div>
      </div>

      <el-form class="login-form" label-position="top" @submit.prevent="submitLogin">
        <el-form-item :label="t('auth.username')">
          <el-input
            v-model="form.username"
            autocomplete="username"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item :label="t('auth.password')">
          <el-input
            v-model="form.password"
            autocomplete="current-password"
            size="large"
            type="password"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-checkbox v-model="form.rememberMe">{{ t('auth.rememberMe') }}</el-checkbox>
        <el-button
          class="login-button"
          native-type="submit"
          size="large"
          type="primary"
          :disabled="!form.username || !form.password"
          :loading="submitting"
        >
          {{ t('auth.login') }}
        </el-button>
      </el-form>

      <template v-if="oauthProviders.length > 0">
        <el-divider>{{ t('auth.enterpriseLogin') }}</el-divider>
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

      <p v-if="oauthCallbackLoading" class="oauth-callback-status">
        {{ t('auth.oauthCallbackLoading') }}
      </p>
    </section>
  </main>
</template>
