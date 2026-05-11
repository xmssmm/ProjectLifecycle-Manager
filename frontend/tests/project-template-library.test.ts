import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createProjectCategory,
  createProjectTag,
  createTemplateFromProject,
  instantiateProjectTemplate,
  listProjectCategories,
  listProjectTags,
  listProjectTemplates,
} from '@/api/projectTemplates';
import ProjectTemplateLibrary from '@/views/admin/ProjectTemplateLibrary.vue';

vi.mock('@/api/projectTemplates', () => ({
  createProjectCategory: vi.fn(),
  createProjectTag: vi.fn(),
  createTemplateFromProject: vi.fn(),
  instantiateProjectTemplate: vi.fn(),
  listProjectCategories: vi.fn(),
  listProjectTags: vi.fn(),
  listProjectTemplates: vi.fn(),
}));

describe('ProjectTemplateLibrary', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listProjectCategories).mockResolvedValue([category]);
    vi.mocked(listProjectTags).mockResolvedValue([tag]);
    vi.mocked(listProjectTemplates).mockResolvedValue([template]);
    vi.mocked(createProjectCategory).mockResolvedValue(category);
    vi.mocked(createProjectTag).mockResolvedValue(tag);
    vi.mocked(createTemplateFromProject).mockResolvedValue(template);
    vi.mocked(instantiateProjectTemplate).mockResolvedValue(project);
  });

  it('renders taxonomy, creates templates, and instantiates projects', async () => {
    const wrapper = mount(ProjectTemplateLibrary, { global: { stubs } });
    await flushPromises();

    expect(wrapper.text()).toContain('档案平台模板');
    expect(wrapper.text()).toContain('软件项目');
    expect(wrapper.text()).toContain('档案');

    await wrapper.find('[data-test="template-source-project"]').setValue(template.source_project_id);
    await wrapper.find('[data-test="template-name"]').setValue('档案平台模板');
    await wrapper.find('[data-test="create-template"]').trigger('click');
    await flushPromises();

    expect(createTemplateFromProject).toHaveBeenCalledWith(
      expect.objectContaining({
        name: '档案平台模板',
        source_project_id: template.source_project_id,
      }),
    );

    await wrapper.find('[data-test="instantiate-template"]').trigger('click');
    await flushPromises();

    expect(instantiateProjectTemplate).toHaveBeenCalledWith(template.id, {
      dept_id: template.owner_dept_id,
      name: `${template.name} 项目`,
    });
  });
});

const category = {
  code: 'software',
  description: null,
  id: 'category-1',
  is_active: true,
  name: '软件项目',
};

const tag = {
  code: 'archive',
  color: '#2f6fed',
  id: 'tag-1',
  is_active: true,
  name: '档案',
};

const template = {
  category_id: category.id,
  created_at: '2026-06-01T00:00:00Z',
  default_task_checklist: [],
  description: '来自已完成项目',
  document_requirements_snapshot: [],
  field_defaults: {
    expected_finish_date: '2026-12-31',
    remark: null,
    total_budget: '800000.00',
  },
  id: 'template-1',
  is_active: true,
  name: '档案平台模板',
  owner_dept_id: 'dept-1',
  owner_id: 'admin-1',
  phase_snapshot: [],
  project_type_id: null,
  scope: 'department' as const,
  source_project_id: 'project-1',
  source_project_no: 'Z-2026-0007',
  tag_ids: [tag.id],
  updated_at: '2026-06-01T00:00:00Z',
};

const project = {
  created_at: '2026-06-01T00:00:00Z',
  creator_id: 'admin-1',
  dept_id: 'dept-1',
  expected_finish_date: '2026-12-31',
  id: 'project-2',
  name: '档案平台模板 项目',
  project_no: 'Z-2026-0012',
  remark: null,
  spent_amount: '0.00',
  status: 'pending_review' as const,
  total_budget: '800000.00',
  updated_at: '2026-06-01T00:00:00Z',
};

const stubs = {
  DataTable: {
    props: ['rows'],
    template:
      '<table><tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.name }}</td><td><slot name="tags" :row="row" /></td><td><slot name="actions" :row="row" /></td></tr></tbody></table>',
  },
  ElButton: {
    props: ['disabled'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElCheckbox: {
    props: ['modelValue', 'label'],
    template:
      '<label><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', label)" />{{ label }}<slot /></label>',
  },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElOption: { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElTag: { template: '<span><slot /></span>' },
};
