import { defineStore } from 'pinia';

import { getDashboard } from '@/api/dashboard';
import type { DashboardRead, DashboardRoleScope } from '@/types/dashboard';

interface DashboardState {
  dashboard: DashboardRead | null;
  error: string | null;
  lastLoadedAt: string | null;
  loading: boolean;
  roleScope: DashboardRoleScope | null;
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): DashboardState => ({
    dashboard: null,
    error: null,
    lastLoadedAt: null,
    loading: false,
    roleScope: null,
  }),
  actions: {
    async fetchDashboard(roleScope: DashboardRoleScope) {
      this.loading = true;
      this.error = null;
      try {
        const dashboard = await getDashboard(roleScope);
        this.dashboard = dashboard;
        this.roleScope = roleScope;
        this.lastLoadedAt = dashboard.generated_at;
        return dashboard;
      } catch (error) {
        this.error = error instanceof Error ? error.message : '加载驾驶舱失败';
        throw error;
      } finally {
        this.loading = false;
      }
    },
  },
});
