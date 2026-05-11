<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import {
  bindOAuthProvider,
  listOAuthBindings,
  listOAuthProviders,
  startOAuthLogin,
  unbindOAuthProvider,
} from '@/api/oauth';
import { useAuthStore } from '@/stores/useAuthStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { useProfileStore } from '@/stores/useProfileStore';
import type {
  NotificationChannel,
  NotificationChannels,
  NotificationDeliveryMode,
  NotificationPreferenceRead,
} from '@/types/notifications';
import type { OAuthBindingRead, OAuthProviderRead } from '@/types/oauth';
import { ROLE_LABELS, STATUS_LABELS } from '@/types/users';
import { DEFAULT_USER_TIMEZONE } from '@/utils/timezone';

const authStore = useAuthStore();
const notificationStore = useNotificationStore();
const profileStore = useProfileStore();
const route = useRoute();
const router = useRouter();

const form = reactive({
  email: '',
  timezone: DEFAULT_USER_TIMEZONE,
});
const notificationPreferenceForm = ref<NotificationPreferenceRead[]>([]);
const notificationDeliveryMode = ref<NotificationDeliveryMode>('real_time');
const notificationMode = ref<NotificationPreferenceMode>('all');
const oauthProviders = ref<OAuthProviderRead[]>([]);
const oauthBindings = ref<OAuthBindingRead[]>([]);
const oauthBusyProvider = ref<string | null>(null);

const profile = computed(() => profileStore.profile);

onMounted(async () => {
  if (!authStore.user) {
    return;
  }
  await completeOAuthBindingIfPresent();
  await Promise.all([
    profileStore.fetchProfile(authStore.user.id),
    loadNotificationPreferences(),
    loadOAuthBindings(),
  ]);
  form.email = profile.value?.email ?? '';
  form.timezone = profile.value?.timezone ?? DEFAULT_USER_TIMEZONE;
});

async function submitProfile(): Promise<void> {
  if (!authStore.user) {
    return;
  }

  await profileStore.updateProfile(authStore.user.id, {
    email: form.email.trim() || null,
    timezone: form.timezone.trim() || DEFAULT_USER_TIMEZONE,
  });
  await authStore.loadCurrentUser();
  ElMessage.success('个人信息已更新');
}
async function loadNotificationPreferences(): Promise<void> {
  const result = await notificationStore.fetchPreferences();
  notificationPreferenceForm.value = clonePreferences(result.items);
  notificationDeliveryMode.value = inferNotificationDeliveryMode(notificationPreferenceForm.value);
  notificationMode.value = inferNotificationMode(notificationPreferenceForm.value);
}

function applyNotificationMode(value: string | number | boolean): void {
  const mode = String(value) as NotificationPreferenceMode;
  if (!notificationModes.includes(mode)) {
    return;
  }
  notificationMode.value = mode;
  if (mode === 'custom') {
    return;
  }
  notificationPreferenceForm.value = notificationPreferenceForm.value.map((preference) => ({
    ...preference,
    enabled: mode === 'all' ? true : preference.direct_related,
    channels: {
      ...preference.channels,
      in_app: mode === 'all' ? true : preference.direct_related,
    },
  }));
}

function setNotificationPreference(scenario: string, enabled: boolean): void {
  notificationPreferenceForm.value = notificationPreferenceForm.value.map((preference) =>
    preference.scenario === scenario
      ? { ...preference, enabled, channels: { ...preference.channels, in_app: enabled } }
      : preference,
  );
  notificationMode.value = inferNotificationMode(notificationPreferenceForm.value);
}

function setNotificationPreferenceValue(scenario: string, value: unknown): void {
  setNotificationPreference(scenario, Boolean(value));
}

function applyNotificationDeliveryMode(value: string | number | boolean): void {
  const deliveryMode = String(value) as NotificationDeliveryMode;
  if (!notificationDeliveryModes.includes(deliveryMode)) {
    return;
  }
  notificationDeliveryMode.value = deliveryMode;
  notificationPreferenceForm.value = notificationPreferenceForm.value.map((preference) => ({
    ...preference,
    delivery_mode: deliveryMode,
  }));
}

function setNotificationChannel(
  scenario: string,
  channel: NotificationChannel,
  enabled: boolean,
): void {
  notificationPreferenceForm.value = notificationPreferenceForm.value.map((preference) => {
    if (preference.scenario !== scenario) {
      return preference;
    }
    const channels = { ...preference.channels, [channel]: enabled };
    return {
      ...preference,
      channels,
      enabled: channel === 'in_app' ? enabled : preference.enabled,
    };
  });
  notificationMode.value = inferNotificationMode(notificationPreferenceForm.value);
}

function setNotificationChannelValue(
  scenario: string,
  channel: NotificationChannel,
  value: unknown,
): void {
  setNotificationChannel(scenario, channel, Boolean(value));
}

async function saveNotificationPreferences(): Promise<void> {
  const result = await notificationStore.savePreferences(
    notificationPreferenceForm.value.map((preference) => ({
      scenario: preference.scenario,
      enabled: preference.enabled,
      delivery_mode: preference.delivery_mode,
      channels: preference.channels,
    })),
  );
  notificationPreferenceForm.value = clonePreferences(result.items);
  notificationDeliveryMode.value = inferNotificationDeliveryMode(notificationPreferenceForm.value);
  notificationMode.value = inferNotificationMode(notificationPreferenceForm.value);
  ElMessage.success('通知偏好已保存');
}

async function loadOAuthBindings(): Promise<void> {
  try {
    const [providers, bindings] = await Promise.all([
      listOAuthProviders(),
      listOAuthBindings(),
    ]);
    oauthProviders.value = providers;
    oauthBindings.value = bindings;
  } catch {
    oauthProviders.value = [];
    oauthBindings.value = [];
  }
}

async function startOAuthBinding(provider: string): Promise<void> {
  oauthBusyProvider.value = provider;
  try {
    const started = await startOAuthLogin(provider, { purpose: 'bind' });
    globalThis.location.assign(started.authorization_url);
  } catch {
    ElMessage.error('企业账号绑定暂不可用');
  } finally {
    oauthBusyProvider.value = null;
  }
}

async function unbindOAuth(provider: string): Promise<void> {
  oauthBusyProvider.value = provider;
  try {
    await unbindOAuthProvider(provider);
    await loadOAuthBindings();
    ElMessage.success('企业账号绑定已解除');
  } finally {
    oauthBusyProvider.value = null;
  }
}

async function completeOAuthBindingIfPresent(): Promise<void> {
  const action = routeQueryString('oauth_action');
  const provider = routeQueryString('oauth_provider');
  const code = routeQueryString('code');
  const state = routeQueryString('state');
  if (action !== 'bind' || !provider || !code || !state) {
    return;
  }

  try {
    await bindOAuthProvider(provider, { code, state });
    ElMessage.success('企业账号已绑定');
    await router.replace({ name: 'profile' });
  } catch {
    ElMessage.error('企业账号绑定失败，请重新尝试');
  }
}

function getOAuthBinding(provider: string): OAuthBindingRead | undefined {
  return oauthBindings.value.find((binding) => binding.provider === provider);
}

function routeQueryString(key: string): string | null {
  const value = route.query[key];
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : null;
  }
  return typeof value === 'string' && value ? value : null;
}

function clonePreferences(
  preferences: NotificationPreferenceRead[],
): NotificationPreferenceRead[] {
  return preferences.map((preference) => ({
    ...preference,
    channels: normalizeChannels(preference.channels, preference.enabled),
  }));
}

function inferNotificationMode(
  preferences: NotificationPreferenceRead[],
): NotificationPreferenceMode {
  if (preferences.length === 0 || preferences.every((preference) => preference.enabled)) {
    return 'all';
  }
  if (preferences.every((preference) => preference.enabled === preference.direct_related)) {
    return 'direct';
  }
  return 'custom';
}

function inferNotificationDeliveryMode(
  preferences: NotificationPreferenceRead[],
): NotificationDeliveryMode {
  if (
    preferences.length > 0 &&
    preferences.every((preference) => preference.delivery_mode === 'daily_digest')
  ) {
    return 'daily_digest';
  }
  return 'real_time';
}

type NotificationPreferenceMode = 'all' | 'direct' | 'custom';

const notificationModes: NotificationPreferenceMode[] = ['all', 'direct', 'custom'];
const notificationDeliveryModes: NotificationDeliveryMode[] = ['real_time', 'daily_digest'];
const notificationChannels: NotificationChannel[] = ['in_app', 'email', 'wework', 'dingtalk'];
const notificationChannelLabels: Record<NotificationChannel, string> = {
  dingtalk: '钉钉',
  email: '邮件',
  in_app: '站内',
  wework: '企业微信',
};

function normalizeChannels(
  channels: Partial<NotificationChannels> | undefined,
  enabled: boolean,
): NotificationChannels {
  return {
    dingtalk: channels?.dingtalk ?? false,
    email: channels?.email ?? false,
    in_app: channels?.in_app ?? enabled,
    wework: channels?.wework ?? false,
  };
}
</script>

<template>
  <section class="admin-page profile-page">
    <div class="admin-page__header">
      <div>
        <h2>个人信息</h2>
        <p>查看账号基础信息，并维护自己的邮箱。</p>
      </div>
    </div>

    <div class="admin-page__table profile-panel">
      <el-descriptions v-if="profile" :column="2" border>
        <el-descriptions-item label="用户名">{{ profile.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ ROLE_LABELS[profile.role] }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          {{ STATUS_LABELS[profile.status] }}
        </el-descriptions-item>
        <el-descriptions-item label="部门 ID">{{ profile.dept_id ?? '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-form class="profile-form" label-width="96px">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" data-test="profile-email" placeholder="可留空" />
        </el-form-item>
        <el-form-item label="时区">
          <el-input
            v-model="form.timezone"
            data-test="profile-timezone"
            placeholder="Asia/Shanghai"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            data-test="profile-save"
            :loading="profileStore.saving"
            type="primary"
            @click="submitProfile"
          >
            保存
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="admin-page__table profile-panel notification-preferences">
      <div class="profile-section-header">
        <h3>通知偏好</h3>
      </div>

      <el-radio-group
        v-model="notificationMode"
        class="notification-preferences__modes"
        data-test="notification-preference-mode"
        @change="applyNotificationMode"
      >
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="direct">仅直接相关</el-radio-button>
        <el-radio-button value="custom">自定义</el-radio-button>
      </el-radio-group>

      <el-radio-group
        v-model="notificationDeliveryMode"
        class="notification-preferences__modes"
        data-test="notification-delivery-mode"
        @change="applyNotificationDeliveryMode"
      >
        <el-radio-button value="real_time">实时通知</el-radio-button>
        <el-radio-button value="daily_digest">每日摘要</el-radio-button>
      </el-radio-group>

      <div class="notification-preferences__list">
        <div
          v-for="preference in notificationPreferenceForm"
          :key="preference.scenario"
          class="notification-preferences__item"
        >
          <div class="notification-preferences__text">
            <strong>{{ preference.label }}</strong>
            <span>{{ preference.description }}</span>
          </div>
          <el-switch
            :data-test="`notification-preference-${preference.scenario}`"
            :model-value="preference.enabled"
            @update:model-value="setNotificationPreferenceValue(preference.scenario, $event)"
          />
          <div class="notification-preferences__channels">
            <el-switch
              v-for="channel in notificationChannels"
              :key="channel"
              :active-text="notificationChannelLabels[channel]"
              :data-test="`notification-channel-${preference.scenario}-${channel}`"
              :model-value="preference.channels[channel]"
              @update:model-value="
                setNotificationChannelValue(preference.scenario, channel, $event)
              "
            />
          </div>
        </div>
      </div>

      <el-button
        data-test="notification-preferences-save"
        :loading="notificationStore.preferencesSaving"
        type="primary"
        @click="saveNotificationPreferences"
      >
        保存通知偏好
      </el-button>
    </div>

    <div v-if="oauthProviders.length > 0" class="admin-page__table profile-panel oauth-bindings">
      <div class="profile-section-header">
        <h3>企业账号绑定</h3>
      </div>

      <div class="oauth-bindings__list">
        <div
          v-for="provider in oauthProviders"
          :key="provider.provider"
          class="oauth-bindings__item"
          :data-test="`oauth-binding-${provider.provider}`"
        >
          <div class="oauth-bindings__text">
            <strong>{{ provider.label }}</strong>
            <span v-if="getOAuthBinding(provider.provider)">
              已绑定 {{ getOAuthBinding(provider.provider)?.email ?? '外部账号' }}
            </span>
            <span v-else>未绑定</span>
          </div>
          <el-button
            v-if="getOAuthBinding(provider.provider)"
            :data-test="`oauth-unbind-${provider.provider}`"
            :loading="oauthBusyProvider === provider.provider"
            @click="unbindOAuth(provider.provider)"
          >
            解绑
          </el-button>
          <el-button
            v-else
            :data-test="`oauth-bind-${provider.provider}`"
            :loading="oauthBusyProvider === provider.provider"
            type="primary"
            @click="startOAuthBinding(provider.provider)"
          >
            绑定
          </el-button>
        </div>
      </div>
    </div>
  </section>
</template>
