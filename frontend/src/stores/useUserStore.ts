import { defineStore } from 'pinia';

import {
  createUser as createUserRequest,
  disableUser as disableUserRequest,
  listUsers,
  resetUserPassword,
  updateUser as updateUserRequest,
} from '@/api/users';
import type {
  PasswordResetPayload,
  UserCreatePayload,
  UserListQuery,
  UserRead,
  UserUpdatePayload,
} from '@/types/users';

interface UserState {
  filters: Pick<UserListQuery, 'role'>;
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
  users: UserRead[];
}

export const useUserStore = defineStore('users', {
  state: (): UserState => ({
    filters: {},
    loading: false,
    page: 1,
    pageSize: 20,
    total: 0,
    users: [],
  }),
  actions: {
    async fetchUsers(query?: Partial<UserListQuery>) {
      this.page = query?.page ?? this.page;
      this.pageSize = query?.pageSize ?? this.pageSize;
      this.filters = { role: query?.role };
      this.loading = true;
      try {
        const result = await listUsers({
          page: this.page,
          pageSize: this.pageSize,
          role: this.filters.role,
        });
        this.users = result.items;
        this.total = result.total;
        this.page = result.page;
        this.pageSize = result.page_size;
      } finally {
        this.loading = false;
      }
    },
    async createUser(payload: UserCreatePayload) {
      await createUserRequest(payload);
      await this.refresh();
    },
    async updateUser(userId: string, payload: UserUpdatePayload) {
      await updateUserRequest(userId, payload);
      await this.refresh();
    },
    async disableUser(userId: string) {
      await disableUserRequest(userId);
      await this.refresh();
    },
    async resetPassword(userId: string, payload: PasswordResetPayload) {
      await resetUserPassword(userId, payload);
      await this.refresh();
    },
    async refresh() {
      await this.fetchUsers({
        page: this.page,
        pageSize: this.pageSize,
        role: this.filters.role,
      });
    },
  },
});
