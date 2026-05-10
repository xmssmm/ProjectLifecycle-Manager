import { defineStore } from 'pinia';

import {
  batchHandoverSubProjects as batchHandoverSubProjectsRequest,
  createUser as createUserRequest,
  disableUser as disableUserRequest,
  listActiveSubProjectsForLeader,
  listSubProjectHandovers,
  listUsers,
  resetUserPassword,
  updateUser as updateUserRequest,
} from '@/api/users';
import type {
  SubProjectBatchHandoverItem,
  SubProjectBatchHandoverRead,
  SubProjectHandoverQuery,
  SubProjectHandoverRead,
  SubProjectRead,
} from '@/types/projects';
import type {
  PasswordResetPayload,
  UserCreatePayload,
  UserListQuery,
  UserRead,
  UserUpdatePayload,
} from '@/types/users';

interface UserState {
  activeSubProjects: SubProjectRead[];
  filters: Pick<UserListQuery, 'role'>;
  handoverHistory: SubProjectHandoverRead[];
  handoverHistoryFilters: Partial<
    Pick<SubProjectHandoverQuery, 'fromUserId' | 'subProjectId' | 'toUserId'>
  >;
  handoverHistoryPage: number;
  handoverHistoryPageSize: number;
  handoverHistoryTotal: number;
  handoverLoading: boolean;
  handoverSubmitting: boolean;
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
  users: UserRead[];
}

export const useUserStore = defineStore('users', {
  state: (): UserState => ({
    activeSubProjects: [],
    filters: {},
    handoverHistory: [],
    handoverHistoryFilters: {},
    handoverHistoryPage: 1,
    handoverHistoryPageSize: 20,
    handoverHistoryTotal: 0,
    handoverLoading: false,
    handoverSubmitting: false,
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
    async fetchActiveSubProjectsForLeader(userId: string) {
      this.handoverLoading = true;
      this.activeSubProjects = [];
      try {
        const result = await listActiveSubProjectsForLeader(userId);
        this.activeSubProjects = result.items;
        return result;
      } finally {
        this.handoverLoading = false;
      }
    },
    async batchHandoverSubProjects(
      userId: string,
      payload: SubProjectBatchHandoverItem[],
    ): Promise<SubProjectBatchHandoverRead> {
      this.handoverSubmitting = true;
      try {
        const result = await batchHandoverSubProjectsRequest(userId, payload);
        const handedOverIds = new Set(result.items.map((item) => item.id));
        this.activeSubProjects = this.activeSubProjects.filter(
          (item) => !handedOverIds.has(item.id),
        );
        return result;
      } finally {
        this.handoverSubmitting = false;
      }
    },
    async fetchSubProjectHandovers(query?: SubProjectHandoverQuery) {
      const nextQuery = {
        fromUserId: query?.fromUserId ?? this.handoverHistoryFilters.fromUserId,
        page: query?.page ?? this.handoverHistoryPage,
        pageSize: query?.pageSize ?? this.handoverHistoryPageSize,
        subProjectId: query?.subProjectId ?? this.handoverHistoryFilters.subProjectId,
        toUserId: query?.toUserId ?? this.handoverHistoryFilters.toUserId,
      };
      this.handoverLoading = true;
      this.handoverHistoryFilters = {
        fromUserId: nextQuery.fromUserId,
        subProjectId: nextQuery.subProjectId,
        toUserId: nextQuery.toUserId,
      };
      try {
        const result = await listSubProjectHandovers(nextQuery);
        this.handoverHistory = result.items;
        this.handoverHistoryPage = result.page;
        this.handoverHistoryPageSize = result.page_size;
        this.handoverHistoryTotal = result.total;
        return result;
      } finally {
        this.handoverLoading = false;
      }
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
