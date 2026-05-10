import { defineStore } from 'pinia';

import {
  createMainProject as createMainProjectRequest,
  getMainProject,
  listMainProjects,
  submitMainProject as submitMainProjectRequest,
  updateMainProject as updateMainProjectRequest,
} from '@/api/mainProjects';
import { listSubProjects } from '@/api/subProjects';
import type {
  MainProjectCreatePayload,
  MainProjectListQuery,
  MainProjectRead,
  MainProjectUpdatePayload,
  SubProjectRead,
} from '@/types/projects';

interface MainProjectState {
  currentProject: MainProjectRead | null;
  currentSubProjects: SubProjectRead[];
  detailLoading: boolean;
  listQuery: MainProjectListQuery;
  loading: boolean;
  page: number;
  pageSize: number;
  projects: MainProjectRead[];
  total: number;
}

export const useMainProjectStore = defineStore('main-projects', {
  state: (): MainProjectState => ({
    currentProject: null,
    currentSubProjects: [],
    detailLoading: false,
    listQuery: { page: 1, pageSize: 20 },
    loading: false,
    page: 1,
    pageSize: 20,
    projects: [],
    total: 0,
  }),
  actions: {
    async fetchMainProjects(query?: MainProjectListQuery) {
      const nextQuery = query ?? this.listQuery;
      this.loading = true;
      this.listQuery = nextQuery;
      try {
        const result = await listMainProjects(nextQuery);
        this.projects = result.items;
        this.page = result.page;
        this.pageSize = result.page_size;
        this.total = result.total;
      } finally {
        this.loading = false;
      }
    },
    async fetchMainProjectDetail(projectId: string) {
      this.detailLoading = true;
      try {
        const [project, subProjects] = await Promise.all([
          getMainProject(projectId),
          listSubProjects({ page: 1, pageSize: 100 }),
        ]);
        this.currentProject = project;
        this.currentSubProjects = subProjects.items.filter(
          (subProject) => subProject.main_project_id === projectId,
        );
        return project;
      } finally {
        this.detailLoading = false;
      }
    },
    async createMainProject(payload: MainProjectCreatePayload) {
      const project = await createMainProjectRequest(payload);
      this.currentProject = project;
      return project;
    },
    async updateMainProject(projectId: string, payload: MainProjectUpdatePayload) {
      const project = await updateMainProjectRequest(projectId, payload);
      this.currentProject = project;
      return project;
    },
    async submitMainProject(projectId: string) {
      const project = await submitMainProjectRequest(projectId);
      this.currentProject = project;
      return project;
    },
  },
});
