import { defineStore } from 'pinia';

import {
  createMainProject as createMainProjectRequest,
  getMainProject,
  getProjectProgressFunnel,
  listMainProjects,
  reviewMainProject as reviewMainProjectRequest,
  submitMainProject as submitMainProjectRequest,
  updateMainProject as updateMainProjectRequest,
} from '@/api/mainProjects';
import { listSubProjects } from '@/api/subProjects';
import type {
  MainProjectCreatePayload,
  MainProjectListQuery,
  MainProjectRead,
  MainProjectReviewPayload,
  MainProjectUpdatePayload,
  ProjectProgressFunnelRead,
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
  progressFunnel: ProjectProgressFunnelRead | null;
  progressFunnelLoading: boolean;
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
    progressFunnel: null,
    progressFunnelLoading: false,
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
      this.progressFunnelLoading = true;
      this.progressFunnel = null;
      try {
        const [project, subProjects, progressFunnel] = await Promise.all([
          getMainProject(projectId),
          listSubProjects({ page: 1, pageSize: 100 }),
          getProjectProgressFunnel(projectId),
        ]);
        this.currentProject = project;
        this.progressFunnel = progressFunnel;
        this.currentSubProjects = subProjects.items.filter(
          (subProject) => subProject.main_project_id === projectId,
        );
        return project;
      } finally {
        this.detailLoading = false;
        this.progressFunnelLoading = false;
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
    async reviewMainProject(projectId: string, payload: MainProjectReviewPayload) {
      const project = await reviewMainProjectRequest(projectId, payload);
      this.currentProject = project;
      return project;
    },
  },
});
