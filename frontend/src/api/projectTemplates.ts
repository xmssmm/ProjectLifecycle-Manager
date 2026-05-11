import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
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

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listProjectCategories(
  client: AxiosInstance = apiClient,
): Promise<ProjectCategoryRead[]> {
  const response = await client.get<ApiResponse<ProjectCategoryRead[]>>(
    '/project-templates/categories',
  );
  return response.data.data;
}

export async function createProjectCategory(
  payload: ProjectCategoryCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<ProjectCategoryRead> {
  const response = await client.post<ApiResponse<ProjectCategoryRead>>(
    '/project-templates/categories',
    payload,
  );
  return response.data.data;
}

export async function listProjectTags(
  client: AxiosInstance = apiClient,
): Promise<ProjectTagRead[]> {
  const response = await client.get<ApiResponse<ProjectTagRead[]>>('/project-templates/tags');
  return response.data.data;
}

export async function createProjectTag(
  payload: ProjectTagCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<ProjectTagRead> {
  const response = await client.post<ApiResponse<ProjectTagRead>>(
    '/project-templates/tags',
    payload,
  );
  return response.data.data;
}

export async function listProjectTemplates(
  tagId?: string,
  client: AxiosInstance = apiClient,
): Promise<ProjectTemplateRead[]> {
  const response = await client.get<ApiResponse<ProjectTemplateRead[]>>(
    '/project-templates/templates',
    { params: tagId ? { tag_id: tagId } : undefined },
  );
  return response.data.data;
}

export async function createTemplateFromProject(
  payload: ProjectTemplateCreateFromProjectPayload,
  client: AxiosInstance = apiClient,
): Promise<ProjectTemplateRead> {
  const response = await client.post<ApiResponse<ProjectTemplateRead>>(
    '/project-templates/templates/from-project',
    payload,
  );
  return response.data.data;
}

export async function instantiateProjectTemplate(
  templateId: string,
  payload: ProjectTemplateInstantiatePayload,
  client: AxiosInstance = apiClient,
): Promise<MainProjectRead> {
  const response = await client.post<ApiResponse<MainProjectRead>>(
    `/project-templates/templates/${templateId}/instantiate`,
    payload,
  );
  return response.data.data;
}
