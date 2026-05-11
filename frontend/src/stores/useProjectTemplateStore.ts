import { defineStore } from 'pinia';

import {
  createProjectCategory,
  createProjectTag,
  createTemplateFromProject,
  instantiateProjectTemplate,
  listProjectCategories,
  listProjectTags,
  listProjectTemplates,
} from '@/api/projectTemplates';
import type { MainProjectRead } from '@/types/projects';
import type {
  ProjectCategoryCreatePayload,
  ProjectCategoryRead,
  ProjectTagCreatePayload,
  ProjectTagRead,
  ProjectTemplateCreateFromProjectPayload,
  ProjectTemplateInstantiatePayload,
  ProjectTemplateRead,
} from '@/types/projectTemplates';

interface ProjectTemplateState {
  categories: ProjectCategoryRead[];
  loading: boolean;
  tags: ProjectTagRead[];
  templates: ProjectTemplateRead[];
}

export const useProjectTemplateStore = defineStore('projectTemplates', {
  state: (): ProjectTemplateState => ({
    categories: [],
    loading: false,
    tags: [],
    templates: [],
  }),
  actions: {
    async fetchAll(tagId?: string): Promise<void> {
      this.loading = true;
      try {
        const [categories, tags, templates] = await Promise.all([
          listProjectCategories(),
          listProjectTags(),
          listProjectTemplates(tagId),
        ]);
        this.categories = categories;
        this.tags = tags;
        this.templates = templates;
      } finally {
        this.loading = false;
      }
    },
    async createCategory(payload: ProjectCategoryCreatePayload): Promise<ProjectCategoryRead> {
      const category = await createProjectCategory(payload);
      this.categories = [category, ...this.categories.filter((item) => item.id !== category.id)];
      return category;
    },
    async createTag(payload: ProjectTagCreatePayload): Promise<ProjectTagRead> {
      const tag = await createProjectTag(payload);
      this.tags = [tag, ...this.tags.filter((item) => item.id !== tag.id)];
      return tag;
    },
    async createTemplate(
      payload: ProjectTemplateCreateFromProjectPayload,
    ): Promise<ProjectTemplateRead> {
      const template = await createTemplateFromProject(payload);
      this.templates = [template, ...this.templates.filter((item) => item.id !== template.id)];
      return template;
    },
    async instantiateTemplate(
      templateId: string,
      payload: ProjectTemplateInstantiatePayload,
    ): Promise<MainProjectRead> {
      return instantiateProjectTemplate(templateId, payload);
    },
  },
});
