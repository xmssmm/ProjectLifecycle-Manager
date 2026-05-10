import { defineStore } from 'pinia';

import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshAccessToken,
} from '@/api/auth';

export type UserRole =
  | 'admin'
  | 'dept_manager'
  | 'finance_manager'
  | 'proj_leader'
  | 'proj_member';

export interface AuthUser {
  id: string;
  username: string;
  role: UserRole;
  deptId: string | null;
}

interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    accessToken: null,
    user: null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken),
  },
  persist: {
    key: 'project-mgmt-auth',
    paths: ['accessToken', 'user'],
  },
  actions: {
    setAccessToken(token: string | null) {
      this.accessToken = token;
    },
    setUser(user: AuthUser | null) {
      this.user = user;
    },
    clearSession() {
      this.accessToken = null;
      this.user = null;
    },
    async login(username: string, password: string) {
      const tokens = await loginRequest({ username, password });
      this.setAccessToken(tokens.access_token);
      await this.loadCurrentUser();
    },
    async loadCurrentUser() {
      const user = await getCurrentUser();
      this.setUser({
        id: user.id,
        username: user.username,
        role: user.role,
        deptId: user.dept_id,
      });
    },
    async refreshSession() {
      const token = await refreshAccessToken();
      this.setAccessToken(token.access_token);
    },
    async logout() {
      try {
        await logoutRequest();
      } finally {
        this.clearSession();
      }
    },
  },
});
