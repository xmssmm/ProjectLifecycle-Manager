import { defineStore } from 'pinia';

interface AuthState {
  accessToken: string | null;
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    accessToken: null,
  }),
  persist: {
    key: 'project-mgmt-auth',
    paths: ['accessToken'],
  },
  actions: {
    setAccessToken(token: string | null) {
      this.accessToken = token;
    },
  },
});
