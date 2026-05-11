import type { AxiosInstance } from 'axios';

import { apiClient } from '@/api/client';
import type {
  ProjectTypeCreatePayload,
  ProjectTypeRead,
  WorkflowPhaseDefinition,
  WorkflowTemplateCreatePayload,
  WorkflowTemplateRead,
  WorkflowTemplateVersionRead,
} from '@/types/workflows';

interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export async function listProjectTypes(
  client: AxiosInstance = apiClient,
): Promise<ProjectTypeRead[]> {
  const response = await client.get<ApiResponse<ProjectTypeRead[]>>('/workflows/project-types');
  return response.data.data;
}

export async function createProjectType(
  payload: ProjectTypeCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<ProjectTypeRead> {
  const response = await client.post<ApiResponse<ProjectTypeRead>>('/workflows/project-types', {
    code: payload.code,
    description: payload.description ?? null,
    name: payload.name,
  });
  return response.data.data;
}

export async function listWorkflowTemplates(
  client: AxiosInstance = apiClient,
): Promise<WorkflowTemplateRead[]> {
  const response = await client.get<ApiResponse<WorkflowTemplateRead[]>>('/workflows/templates');
  return response.data.data;
}

export async function createWorkflowTemplate(
  payload: WorkflowTemplateCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<WorkflowTemplateRead> {
  const response = await client.post<ApiResponse<WorkflowTemplateRead>>('/workflows/templates', {
    description: payload.description ?? null,
    name: payload.name,
    project_type_id: payload.projectTypeId,
  });
  return response.data.data;
}

export async function updateWorkflowPhaseDefinitions(
  versionId: string,
  phaseDefinitions: WorkflowPhaseDefinition[],
  client: AxiosInstance = apiClient,
): Promise<WorkflowTemplateVersionRead> {
  const response = await client.put<ApiResponse<WorkflowTemplateVersionRead>>(
    `/workflows/template-versions/${versionId}/phase-definitions`,
    { phase_definitions: phaseDefinitions },
  );
  return response.data.data;
}

export async function publishWorkflowTemplateVersion(
  versionId: string,
  client: AxiosInstance = apiClient,
): Promise<WorkflowTemplateVersionRead> {
  const response = await client.post<ApiResponse<WorkflowTemplateVersionRead>>(
    `/workflows/template-versions/${versionId}/publish`,
  );
  return response.data.data;
}
