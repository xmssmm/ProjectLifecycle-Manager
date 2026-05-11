import { defineStore } from 'pinia';

import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshAccessToken,
} from '@/api/auth';
import type { TokenPair } from '@/api/auth';
import type { UserRole, UserStatus } from '@/types/users';

export type { UserRole, UserStatus } from '@/types/users';

export interface AuthUser {
  deptId: string | null;
  email: string | null;
  id: string;
  role: UserRole;
  status: UserStatus;
  timezone?: string;
  username: string;
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
      await this.applyTokenPair(tokens);
    },
    async applyTokenPair(tokens: TokenPair) {
      this.setAccessToken(tokens.access_token);
      await this.loadCurrentUser();
    },
    async loadCurrentUser() {
      const user = await getCurrentUser();
      this.setUser({
        deptId: user.dept_id,
        email: user.email,
        id: user.id,
        role: user.role,
        status: user.status,
        timezone: user.timezone,
        username: user.username,
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
