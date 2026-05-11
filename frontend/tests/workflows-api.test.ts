import { describe, expect, it, vi } from 'vitest';

import {
  createProjectType,
  createWorkflowTemplate,
  listProjectTypes,
  listWorkflowTemplates,
  publishWorkflowTemplateVersion,
  updateWorkflowPhaseDefinitions,
} from '@/api/workflows';

describe('workflows api', () => {
  it('maps workflow management endpoints to backend routes', async () => {
    const client = {
      get: vi.fn((url: string) => {
        if (url === '/workflows/project-types') {
          return Promise.resolve({ data: { data: [projectType] } });
        }
        return Promise.resolve({ data: { data: [template] } });
      }),
      post: vi.fn((url: string) => {
        if (url.endsWith('/publish')) {
          return Promise.resolve({ data: { data: publishedVersion } });
        }
        if (url === '/workflows/templates') {
          return Promise.resolve({ data: { data: template } });
        }
        return Promise.resolve({ data: { data: projectType } });
      }),
      put: vi.fn(() => Promise.resolve({ data: { data: draftVersion } })),
    };

    await expect(listProjectTypes(client as never)).resolves.toEqual([projectType]);
    await expect(listWorkflowTemplates(client as never)).resolves.toEqual([template]);
    await expect(
      createProjectType({ code: 'research', description: '科研流程', name: '科研项目' }, client as never),
    ).resolves.toEqual(projectType);
    await expect(
      createWorkflowTemplate(
        { description: '默认科研流程', name: 'research-default', projectTypeId: 'pt-1' },
        client as never,
      ),
    ).resolves.toEqual(template);
    await expect(
      updateWorkflowPhaseDefinitions('version-1', [phaseDefinition], client as never),
    ).resolves.toEqual(draftVersion);
    await expect(publishWorkflowTemplateVersion('version-1', client as never)).resolves.toEqual(
      publishedVersion,
    );

    expect(client.get).toHaveBeenCalledWith('/workflows/project-types');
    expect(client.get).toHaveBeenCalledWith('/workflows/templates');
    expect(client.post).toHaveBeenCalledWith('/workflows/project-types', {
      code: 'research',
      description: '科研流程',
      name: '科研项目',
    });
    expect(client.post).toHaveBeenCalledWith('/workflows/templates', {
      description: '默认科研流程',
      name: 'research-default',
      project_type_id: 'pt-1',
    });
    expect(client.put).toHaveBeenCalledWith('/workflows/template-versions/version-1/phase-definitions', {
      phase_definitions: [phaseDefinition],
    });
    expect(client.post).toHaveBeenCalledWith('/workflows/template-versions/version-1/publish');
  });
});

const projectType = {
  code: 'research',
  created_at: '2026-05-11T12:00:00Z',
  description: '科研流程',
  id: 'pt-1',
  is_active: true,
  is_builtin: false,
  name: '科研项目',
  updated_at: '2026-05-11T12:00:00Z',
};

const phaseDefinition = {
  allow_parallel: false,
  entry_rules: {},
  key: 'proposal',
  name: '课题申报',
  order: 1,
  required_documents: [],
};

const draftVersion = {
  created_at: '2026-05-11T12:00:00Z',
  id: 'version-1',
  phase_definitions: [phaseDefinition],
  published_at: null,
  status: 'draft',
  template_id: 'template-1',
  updated_at: '2026-05-11T12:00:00Z',
  version_no: 1,
};

const publishedVersion = {
  ...draftVersion,
  published_at: '2026-05-11T12:05:00Z',
  status: 'published',
};

const template = {
  created_at: '2026-05-11T12:00:00Z',
  created_by_id: 'admin-1',
  description: '默认科研流程',
  id: 'template-1',
  name: 'research-default',
  project_type_id: 'pt-1',
  status: 'draft',
  updated_at: '2026-05-11T12:00:00Z',
  versions: [draftVersion],
};
