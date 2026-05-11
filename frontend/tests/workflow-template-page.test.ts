import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createProjectType,
  createWorkflowTemplate,
  listProjectTypes,
  listWorkflowTemplates,
  publishWorkflowTemplateVersion,
  updateWorkflowPhaseDefinitions,
} from '@/api/workflows';
import type { WorkflowTemplateRead, WorkflowTemplateVersionRead } from '@/types/workflows';
import WorkflowTemplateManagement from '@/views/admin/WorkflowTemplateManagement.vue';

vi.mock('@/api/workflows', () => ({
  createProjectType: vi.fn(),
  createWorkflowTemplate: vi.fn(),
  listProjectTypes: vi.fn(),
  listWorkflowTemplates: vi.fn(),
  publishWorkflowTemplateVersion: vi.fn(),
  updateWorkflowPhaseDefinitions: vi.fn(),
}));

describe('WorkflowTemplateManagement', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listProjectTypes).mockResolvedValue([projectType]);
    vi.mocked(listWorkflowTemplates).mockResolvedValue([template]);
    vi.mocked(createProjectType).mockResolvedValue(projectType);
    vi.mocked(createWorkflowTemplate).mockResolvedValue(template);
    vi.mocked(updateWorkflowPhaseDefinitions).mockResolvedValue(draftVersion);
    vi.mocked(publishWorkflowTemplateVersion).mockResolvedValue(publishedVersion);
  });

  it('loads workflow metadata and creates a project type', async () => {
    const wrapper = mount(WorkflowTemplateManagement, { global: { stubs } });
    await flushPromises();

    expect(listProjectTypes).toHaveBeenCalled();
    expect(listWorkflowTemplates).toHaveBeenCalled();
    expect(wrapper.text()).toContain('科研项目');
    expect(wrapper.text()).toContain('research-default');

    await wrapper.find('[data-test="open-create-project-type"]').trigger('click');
    await wrapper.find('[data-test="project-type-code"]').setValue('research');
    await wrapper.find('[data-test="project-type-name"]').setValue('科研项目');
    await wrapper.find('[data-test="project-type-description"]').setValue('科研流程');
    await wrapper.find('[data-test="submit-project-type"]').trigger('click');
    await flushPromises();

    expect(createProjectType).toHaveBeenCalledWith({
      code: 'research',
      description: '科研流程',
      name: '科研项目',
    });
  });

  it('publishes the selected draft version', async () => {
    const wrapper = mount(WorkflowTemplateManagement, { global: { stubs } });
    await flushPromises();

    await wrapper.find('[data-test="publish-template-version"]').trigger('click');
    await flushPromises();

    expect(publishWorkflowTemplateVersion).toHaveBeenCalledWith('version-1');
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

const draftVersion: WorkflowTemplateVersionRead = {
  created_at: '2026-05-11T12:00:00Z',
  id: 'version-1',
  phase_definitions: [phaseDefinition],
  published_at: null,
  status: 'draft',
  template_id: 'template-1',
  updated_at: '2026-05-11T12:00:00Z',
  version_no: 1,
};

const publishedVersion: WorkflowTemplateVersionRead = {
  ...draftVersion,
  published_at: '2026-05-11T12:05:00Z',
  status: 'published',
};

const template: WorkflowTemplateRead = {
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

const stubs = {
  DataTable: {
    props: ['rows'],
    template:
      '<table><tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.name }}</td><td><slot name="actions" :row="row" /></td></tr></tbody></table>',
  },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: {
    props: ['modelValue', 'title'],
    template:
      '<section v-if="modelValue">{{ title }}<slot /><slot name="footer" /></section>',
  },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElOption: { template: '<option><slot /></option>' },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
};
