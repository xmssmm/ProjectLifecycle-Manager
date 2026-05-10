import { defineStore } from 'pinia';

import {
  addSubProjectMember as addSubProjectMemberRequest,
  closeSubProject as closeSubProjectRequest,
  createSubProject as createSubProjectRequest,
  getSubProject,
  listSubProjectMembers,
  listSubProjects,
  removeSubProjectMember as removeSubProjectMemberRequest,
  reviewSubProject as reviewSubProjectRequest,
  submitSubProject as submitSubProjectRequest,
  terminateSubProject as terminateSubProjectRequest,
  updateSubProject as updateSubProjectRequest,
} from '@/api/subProjects';
import type {
  SubProjectCreatePayload,
  SubProjectListQuery,
  SubProjectMemberCreatePayload,
  SubProjectMemberRead,
  SubProjectRead,
  SubProjectReviewPayload,
  SubProjectTerminatePayload,
  SubProjectUpdatePayload,
} from '@/types/projects';

interface SubProjectState {
  currentSubProject: SubProjectRead | null;
  detailLoading: boolean;
  listQuery: SubProjectListQuery;
  loading: boolean;
  members: SubProjectMemberRead[];
  membersLoading: boolean;
  page: number;
  pageSize: number;
  subProjects: SubProjectRead[];
  total: number;
}

export const useSubProjectStore = defineStore('sub-projects', {
  state: (): SubProjectState => ({
    currentSubProject: null,
    detailLoading: false,
    listQuery: { page: 1, pageSize: 20 },
    loading: false,
    members: [],
    membersLoading: false,
    page: 1,
    pageSize: 20,
    subProjects: [],
    total: 0,
  }),
  actions: {
    async fetchSubProjects(query?: SubProjectListQuery) {
      const nextQuery = query ?? this.listQuery;
      this.loading = true;
      this.listQuery = nextQuery;
      try {
        const result = await listSubProjects(nextQuery);
        this.subProjects = result.items;
        this.page = result.page;
        this.pageSize = result.page_size;
        this.total = result.total;
      } finally {
        this.loading = false;
      }
    },
    async fetchSubProjectDetail(subProjectId: string) {
      this.detailLoading = true;
      try {
        const subProject = await getSubProject(subProjectId);
        this.currentSubProject = subProject;
        return subProject;
      } finally {
        this.detailLoading = false;
      }
    },
    async fetchSubProjectMembers(subProjectId: string) {
      this.membersLoading = true;
      try {
        const result = await listSubProjectMembers(subProjectId);
        this.members = result.items;
        return result.items;
      } finally {
        this.membersLoading = false;
      }
    },
    async createSubProject(payload: SubProjectCreatePayload) {
      const subProject = await createSubProjectRequest(payload);
      this.currentSubProject = subProject;
      return subProject;
    },
    async updateSubProject(subProjectId: string, payload: SubProjectUpdatePayload) {
      const subProject = await updateSubProjectRequest(subProjectId, payload);
      this.currentSubProject = subProject;
      return subProject;
    },
    async submitSubProject(subProjectId: string) {
      const subProject = await submitSubProjectRequest(subProjectId);
      this.currentSubProject = subProject;
      return subProject;
    },
    async reviewSubProject(subProjectId: string, payload: SubProjectReviewPayload) {
      const subProject = await reviewSubProjectRequest(subProjectId, payload);
      this.currentSubProject = subProject;
      return subProject;
    },
    async closeSubProject(subProjectId: string) {
      const subProject = await closeSubProjectRequest(subProjectId);
      this.currentSubProject = subProject;
      return subProject;
    },
    async terminateSubProject(subProjectId: string, payload: SubProjectTerminatePayload) {
      const subProject = await terminateSubProjectRequest(subProjectId, payload);
      this.currentSubProject = subProject;
      return subProject;
    },
    async addSubProjectMember(subProjectId: string, payload: SubProjectMemberCreatePayload) {
      const member = await addSubProjectMemberRequest(subProjectId, payload);
      this.members = [
        ...this.members.filter((item) => item.user_id !== member.user_id),
        member,
      ].sort((left, right) => left.joined_at.localeCompare(right.joined_at));
      return member;
    },
    async removeSubProjectMember(subProjectId: string, userId: string) {
      const member = await removeSubProjectMemberRequest(subProjectId, userId);
      this.members = this.members.filter((item) => item.user_id !== userId);
      return member;
    },
  },
});
