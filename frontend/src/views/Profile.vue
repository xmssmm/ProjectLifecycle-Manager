<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { useAuthStore } from '@/stores/useAuthStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { useProfileStore } from '@/stores/useProfileStore';
import type { NotificationDeliveryMode, NotificationPreferenceRead } from '@/types/notifications';
import { ROLE_LABELS, STATUS_LABELS } from '@/types/users';

const authStore = useAuthStore();
const notificationStore = useNotificationStore();
const profileStore = useProfileStore();

const form = reactive({
  email: '',
});
const notificationPreferenceForm = ref<NotificationPreferenceRead[]>([]);
const notificationDeliveryMode = ref<NotificationDeliveryMode>('real_time');
const notificationMode = ref<NotificationPreferenceMode>('all');

const profile = computed(() => profileStore.profile);

onMounted(async () => {
  if (!authStore.user) {
    return;
  }
  await Promise.all([
    profileStore.fetchProfile(authStore.user.id),
    loadNotificationPreferences(),
  ]);
  form.email = profile.value?.email ?? '';
});

async function submitProfile(): Promise<void> {
  if (!authStore.user) {
    return;
  }

  await profileStore.updateProfile(authStore.user.id, {
    email: form.email.trim() || null,
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
  }));
}

function setNotificationPreference(scenario: string, enabled: boolean): void {
  notificationPreferenceForm.value = notificationPreferenceForm.value.map((preference) =>
    preference.scenario === scenario ? { ...preference, enabled } : preference,
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

async function saveNotificationPreferences(): Promise<void> {
  const result = await notificationStore.savePreferences(
    notificationPreferenceForm.value.map((preference) => ({
      scenario: preference.scenario,
      enabled: preference.enabled,
      delivery_mode: preference.delivery_mode,
    })),
  );
  notificationPreferenceForm.value = clonePreferences(result.items);
  notificationDeliveryMode.value = inferNotificationDeliveryMode(notificationPreferenceForm.value);
  notificationMode.value = inferNotificationMode(notificationPreferenceForm.value);
  ElMessage.success('通知偏好已保存');
}

function clonePreferences(
  preferences: NotificationPreferenceRead[],
): NotificationPreferenceRead[] {
  return preferences.map((preference) => ({ ...preference }));
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
  </section>
</template>
