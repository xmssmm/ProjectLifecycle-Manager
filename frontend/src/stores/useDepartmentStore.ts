import { defineStore } from 'pinia';

import {
  createDepartment as createDepartmentRequest,
  deleteDepartment as deleteDepartmentRequest,
  listDepartments,
  updateDepartment as updateDepartmentRequest,
} from '@/api/departments';
import type {
  DepartmentCreatePayload,
  DepartmentRead,
  DepartmentUpdatePayload,
} from '@/types/departments';

interface DepartmentState {
  departments: DepartmentRead[];
  loading: boolean;
  total: number;
}

export const useDepartmentStore = defineStore('departments', {
  state: (): DepartmentState => ({
    departments: [],
    loading: false,
    total: 0,
  }),
  actions: {
    async fetchDepartments() {
      this.loading = true;
      try {
        const departments = await listDepartments();
        this.departments = departments;
        this.total = departments.length;
      } finally {
        this.loading = false;
      }
    },
    async createDepartment(payload: DepartmentCreatePayload) {
      await createDepartmentRequest(payload);
      await this.fetchDepartments();
    },
    async updateDepartment(departmentId: string, payload: DepartmentUpdatePayload) {
      await updateDepartmentRequest(departmentId, payload);
      await this.fetchDepartments();
    },
    async deleteDepartment(departmentId: string) {
      await deleteDepartmentRequest(departmentId);
      await this.fetchDepartments();
    },
  },
});
