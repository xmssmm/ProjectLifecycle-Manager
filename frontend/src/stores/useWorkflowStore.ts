import { defineStore } from 'pinia';

import {
  createProjectType as createProjectTypeRequest,
  createWorkflowTemplate as createWorkflowTemplateRequest,
  listProjectTypes,
  listWorkflowTemplates,
  publishWorkflowTemplateVersion,
  updateWorkflowPhaseDefinitions,
} from '@/api/workflows';
import type {
  ProjectTypeCreatePayload,
  ProjectTypeRead,
  WorkflowPhaseDefinition,
  WorkflowTemplateCreatePayload,
  WorkflowTemplateRead,
  WorkflowTemplateVersionRead,
} from '@/types/workflows';

interface WorkflowState {
  loading: boolean;
  projectTypes: ProjectTypeRead[];
  submitting: boolean;
  templates: WorkflowTemplateRead[];
}

export const useWorkflowStore = defineStore('workflows', {
  state: (): WorkflowState => ({
    loading: false,
    projectTypes: [],
    submitting: false,
    templates: [],
  }),
  actions: {
    async fetchAll() {
      this.loading = true;
      try {
        const [projectTypes, templates] = await Promise.all([
          listProjectTypes(),
          listWorkflowTemplates(),
        ]);
        this.projectTypes = projectTypes;
        this.templates = templates;
      } finally {
        this.loading = false;
      }
    },
    async createProjectType(payload: ProjectTypeCreatePayload): Promise<ProjectTypeRead> {
      this.submitting = true;
      try {
        const result = await createProjectTypeRequest(payload);
        this.projectTypes = [result, ...this.projectTypes.filter((item) => item.id !== result.id)];
        return result;
      } finally {
        this.submitting = false;
      }
    },
    async createTemplate(payload: WorkflowTemplateCreatePayload): Promise<WorkflowTemplateRead> {
      this.submitting = true;
      try {
        const result = await createWorkflowTemplateRequest(payload);
        this.upsertTemplate(result);
        return result;
      } finally {
        this.submitting = false;
      }
    },
    async updatePhaseDefinitions(
      versionId: string,
      phaseDefinitions: WorkflowPhaseDefinition[],
    ): Promise<WorkflowTemplateVersionRead> {
      this.submitting = true;
      try {
        const result = await updateWorkflowPhaseDefinitions(versionId, phaseDefinitions);
        this.upsertVersion(result);
        return result;
      } finally {
        this.submitting = false;
      }
    },
    async publishVersion(versionId: string): Promise<WorkflowTemplateVersionRead> {
      this.submitting = true;
      try {
        const result = await publishWorkflowTemplateVersion(versionId);
        this.upsertVersion(result);
        return result;
      } finally {
        this.submitting = false;
      }
    },
    upsertTemplate(template: WorkflowTemplateRead) {
      this.templates = [template, ...this.templates.filter((item) => item.id !== template.id)];
    },
    upsertVersion(version: WorkflowTemplateVersionRead) {
      this.templates = this.templates.map((template) => {
        if (template.id !== version.template_id) {
          return template;
        }
        return {
          ...template,
          versions: [version, ...template.versions.filter((item) => item.id !== version.id)].sort(
            (a, b) => b.version_no - a.version_no,
          ),
        };
      });
    },
  },
});
