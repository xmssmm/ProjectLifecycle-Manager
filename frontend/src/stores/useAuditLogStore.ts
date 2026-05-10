import { defineStore } from 'pinia';

import { listAuditLogs } from '@/api/auditLogs';
import type { AuditLogListQuery, AuditLogRead } from '@/types/auditLogs';

interface AuditLogState {
  auditLogs: AuditLogRead[];
  filters: Omit<AuditLogListQuery, 'page' | 'pageSize'>;
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
}

export const useAuditLogStore = defineStore('auditLogs', {
  state: (): AuditLogState => ({
    auditLogs: [],
    filters: {},
    loading: false,
    page: 1,
    pageSize: 20,
    total: 0,
  }),
  actions: {
    async fetchAuditLogs(query: AuditLogListQuery = {}) {
      this.page = query.page ?? this.page;
      this.pageSize = query.pageSize ?? this.pageSize;
      this.filters = {
        action: query.action,
        actorId: query.actorId,
        createdFrom: query.createdFrom,
        createdTo: query.createdTo,
        targetId: query.targetId,
        targetType: query.targetType,
      };
      this.loading = true;
      try {
        const result = await listAuditLogs({
          ...this.filters,
          page: this.page,
          pageSize: this.pageSize,
        });
        this.auditLogs = result.items;
        this.page = result.page;
        this.pageSize = result.page_size;
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
  },
});
