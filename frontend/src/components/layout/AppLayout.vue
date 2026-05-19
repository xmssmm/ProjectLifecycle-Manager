<script setup lang="ts">
import {
  Box,
  DataAnalysis,
  Download,
  Folder,
  House,
  List,
  Search,
  Setting,
  SwitchButton,
  Upload,
  User,
} from '@element-plus/icons-vue';
import { computed, type Component } from 'vue';
import { useRouter } from 'vue-router';

import NotificationCenter from '@/components/notification/NotificationCenter.vue';
import { usePermission } from '@/composables/usePermission';
import { getCurrentLocale, localeOptions, setLocale, t, type SupportedLocale } from '@/i18n';
import { useAuthStore } from '@/stores/useAuthStore';
import type { UserRole } from '@/stores/useAuthStore';

interface NavItem {
  disabled?: boolean;
  icon: Component;
  index: string;
  labelKey: string;
  requireRole?: UserRole[];
}

const authStore = useAuthStore();
const { hasRole } = usePermission();
const router = useRouter();

const navItems: NavItem[] = [
  {
    icon: User,
    index: '/handover',
    labelKey: 'nav.selfServiceHandover',
    requireRole: ['admin', 'dept_manager', 'proj_leader'],
  },
  { icon: House, index: '/', labelKey: 'nav.home' },
  { icon: DataAnalysis, index: '/dashboard', labelKey: 'nav.dashboard' },
  { icon: User, index: '/profile', labelKey: 'nav.me' },
  { icon: Folder, index: '/main-projects', labelKey: 'nav.projects' },
  { icon: List, index: '/tasks', labelKey: 'nav.tasks' },
  { icon: DataAnalysis, index: '/reports/custom', labelKey: 'nav.customReports' },
  { icon: DataAnalysis, index: '/analytics/qa', labelKey: 'nav.analyticsQa' },
  { icon: DataAnalysis, index: '/analytics/project-benchmarks', labelKey: 'nav.projectBenchmarks' },
  { icon: DataAnalysis, index: '/analytics/project-risk', labelKey: 'nav.projectRisk' },
  { icon: Search, index: '/search', labelKey: 'nav.search' },
  { icon: List, index: '/revoke-requests', labelKey: 'nav.revoke', requireRole: ['proj_leader'] },
  {
    icon: List,
    index: '/revoke-requests/review',
    labelKey: 'nav.revokeReview',
    requireRole: ['admin', 'dept_manager'],
  },
  { icon: User, index: '/admin/users', labelKey: 'nav.users', requireRole: ['admin'] },
  { icon: Setting, index: '/admin/roles', labelKey: 'nav.roles', requireRole: ['admin'] },
  {
    icon: Setting,
    index: '/admin/departments',
    labelKey: 'nav.departments',
    requireRole: ['admin'],
  },
  { icon: List, index: '/admin/audit-logs', labelKey: 'nav.audit', requireRole: ['admin'] },
  { icon: Setting, index: '/admin/api-keys', labelKey: 'nav.apiKeys', requireRole: ['admin'] },
  { icon: Setting, index: '/admin/webhooks', labelKey: 'nav.webhooks', requireRole: ['admin'] },
  { icon: Setting, index: '/admin/workflows', labelKey: 'nav.workflows', requireRole: ['admin'] },
  {
    icon: Box,
    index: '/admin/project-templates',
    labelKey: 'nav.projectTemplates',
    requireRole: ['admin'],
  },
  { icon: Box, index: '/admin/archives', labelKey: 'nav.archives', requireRole: ['admin'] },
  {
    icon: Upload,
    index: '/admin/imports/projects',
    labelKey: 'nav.imports',
    requireRole: ['admin'],
  },
  {
    icon: Download,
    index: '/admin/exports/database',
    labelKey: 'nav.exports',
    requireRole: ['admin'],
  },
  { icon: User, index: '/admin/handover', labelKey: 'nav.handover', requireRole: ['admin'] },
  { icon: Box, index: '/component-demo', labelKey: 'nav.components', requireRole: ['admin'] },
  {
    disabled: true,
    icon: Setting,
    index: '/admin',
    labelKey: 'nav.management',
    requireRole: ['admin'],
  },
];

const visibleNavItems = computed(() => navItems.filter((item) => hasRole(item.requireRole)));
const currentLocale = computed<SupportedLocale>({
  get: getCurrentLocale,
  set: setLocale,
});

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
        <span class="brand-text">{{ t('app.brand') }}</span>
      </div>
      <el-menu class="nav-menu" default-active="/" router>
        <el-menu-item
          v-for="item in visibleNavItems"
          :key="item.index"
          :disabled="item.disabled"
          :index="item.index"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ t(item.labelKey) }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h1>{{ t('app.title') }}</h1>
          <p>{{ t('app.workspace') }}</p>
        </div>
        <div class="header-account">
          <NotificationCenter />
          <el-segmented
            v-model="currentLocale"
            class="locale-switch"
            :aria-label="t('app.language')"
            :options="localeOptions"
            size="small"
          />
          <router-link class="header-account__name" to="/profile">
            {{ authStore.user?.username ?? t('auth.notLoggedIn') }}
          </router-link>
          <el-tooltip :content="t('auth.logout')" placement="bottom">
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
