import { defineStore } from 'pinia';

import { changeOwnPassword, getUser, updateUser } from '@/api/users';
import type { PasswordChangePayload, UserRead, UserUpdatePayload } from '@/types/users';

interface ProfileState {
  loading: boolean;
  profile: UserRead | null;
  saving: boolean;
}

export const useProfileStore = defineStore('profile', {
  state: (): ProfileState => ({
    loading: false,
    profile: null,
    saving: false,
  }),
  actions: {
    async fetchProfile(userId: string) {
      this.loading = true;
      try {
        this.profile = await getUser(userId);
      } finally {
        this.loading = false;
      }
    },
    async updateProfile(userId: string, payload: UserUpdatePayload) {
      this.saving = true;
      try {
        this.profile = await updateUser(userId, payload);
      } finally {
        this.saving = false;
      }
    },
    async changePassword(payload: PasswordChangePayload) {
      this.saving = true;
      try {
        this.profile = await changeOwnPassword(payload);
      } finally {
        this.saving = false;
      }
    },
  },
});
