<script setup lang="ts">
import { Box, Folder, House, List, Setting, SwitchButton, User } from '@element-plus/icons-vue';
import { computed, type Component } from 'vue';
import { useRouter } from 'vue-router';

import NotificationCenter from '@/components/notification/NotificationCenter.vue';
import { usePermission } from '@/composables/usePermission';
import { useAuthStore } from '@/stores/useAuthStore';
import type { UserRole } from '@/stores/useAuthStore';

interface NavItem {
  disabled?: boolean;
  icon: Component;
  index: string;
  label: string;
  requireRole?: UserRole[];
}

const authStore = useAuthStore();
const { hasRole } = usePermission();
const router = useRouter();

const navItems: NavItem[] = [
  { icon: House, index: '/', label: '工作台' },
  { icon: User, index: '/profile', label: '我的' },
  { icon: Folder, index: '/main-projects', label: '项目' },
  { icon: List, index: '/tasks', label: '任务' },
  { icon: List, index: '/revoke-requests', label: '撤销', requireRole: ['proj_leader'] },
  {
    icon: List,
    index: '/revoke-requests/review',
    label: '撤销审批',
    requireRole: ['admin', 'dept_manager'],
  },
  { icon: User, index: '/admin/users', label: '用户', requireRole: ['admin'] },
  { icon: Setting, index: '/admin/departments', label: '部门', requireRole: ['admin'] },
  { icon: User, index: '/admin/handover', label: '转交', requireRole: ['admin'] },
  { icon: Box, index: '/component-demo', label: '组件', requireRole: ['admin'] },
  { disabled: true, icon: Setting, index: '/admin', label: '管理', requireRole: ['admin'] },
];

const visibleNavItems = computed(() => navItems.filter((item) => hasRole(item.requireRole)));

async function logout() {
  await authStore.logout();
  await router.replace({ name: 'login' });
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="app-sidebar" width="248px">
      <div class="brand">
        <span class="brand-mark">PM</span>
        <span class="brand-text">项目归档</span>
      </div>
      <el-menu class="nav-menu" default-active="/" router>
        <el-menu-item
          v-for="item in visibleNavItems"
          :key="item.index"
          :disabled="item.disabled"
          :index="item.index"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h1>企业项目过程管理与资料归档系统</h1>
          <p>基础工作区</p>
        </div>
        <div class="header-account">
          <NotificationCenter />
          <router-link class="header-account__name" to="/profile">
            {{ authStore.user?.username ?? '未登录' }}
          </router-link>
          <el-tooltip content="退出登录" placement="bottom">
            <el-button circle :icon="SwitchButton" @click="logout" />
          </el-tooltip>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
