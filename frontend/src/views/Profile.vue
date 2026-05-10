<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive } from 'vue';

import { useAuthStore } from '@/stores/useAuthStore';
import { useProfileStore } from '@/stores/useProfileStore';
import { ROLE_LABELS, STATUS_LABELS } from '@/types/users';

const authStore = useAuthStore();
const profileStore = useProfileStore();

const form = reactive({
  email: '',
});

const profile = computed(() => profileStore.profile);

onMounted(async () => {
  if (!authStore.user) {
    return;
  }
  await profileStore.fetchProfile(authStore.user.id);
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
  </section>
</template>
