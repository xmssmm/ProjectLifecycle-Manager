import { defineStore } from 'pinia';

interface AuthState {
  accessToken: string | null;
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    accessToken: null,
  }),
  actions: {
    setAccessToken(token: string | null) {
      this.accessToken = token;
    },
  },
});
