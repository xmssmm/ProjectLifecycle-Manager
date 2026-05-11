import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchProjectRisk } from '@/api/projectRisk';
import ProjectRisk from '@/views/analytics/ProjectRisk.vue';

vi.mock('@/api/projectRisk', () => ({
  fetchProjectRisk: vi.fn(),
}));

describe('ProjectRisk', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(fetchProjectRisk).mockResolvedValue(risk);
  });

  it('renders risk score, reasons, and deterministic summary', async () => {
    const wrapper = mount(ProjectRisk, {
      global: { stubs },
      props: { projectId: 'project-1' },
    });
    await flushPromises();

    expect(fetchProjectRisk).toHaveBeenCalledWith('project-1');
    expect(wrapper.text()).toContain('82');
    expect(wrapper.text()).toContain('high');
    expect(wrapper.text()).toContain('预算偏差');
    expect(wrapper.text()).toContain('建议复核预算');

    await wrapper.find('[data-test="risk-project-id"]').setValue('project-2');
    await wrapper.find('[data-test="run-risk"]').trigger('click');
    await flushPromises();

    expect(fetchProjectRisk).toHaveBeenLastCalledWith('project-2');
  });
});

const risk = {
  actions: ['建议复核预算', '压实逾期任务责任人'],
  level: 'high' as const,
  project_id: 'project-1',
  reasons: [
    {
      code: 'budget_variance',
      message: '预算偏差达到 80.00%',
      score: 25,
      severity: 'high',
    },
    {
      code: 'task_overdue',
      message: '任务逾期率达到 80.00%',
      score: 25,
      severity: 'high',
    },
  ],
  score: 82,
  summary: {
    recommendations: ['建议复核预算'],
    source: 'rules' as const,
    text: '预算偏差达到 80.00%；任务逾期率达到 80.00%',
  },
};

const stubs = {
  ElButton: {
    props: ['disabled', 'loading'],
    template:
      '<button type="button" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
  },
  ElEmpty: { props: ['description'], template: '<div>{{ description }}</div>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElProgress: {
    props: ['percentage', 'status'],
    template: '<div>{{ percentage }} {{ status }}</div>',
  },
  ElSkeleton: { template: '<div><slot /></div>' },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
};
