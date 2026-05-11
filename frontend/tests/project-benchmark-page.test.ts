import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchProjectBenchmark } from '@/api/projectBenchmarks';
import ProjectBenchmark from '@/views/analytics/ProjectBenchmark.vue';

vi.mock('@/api/projectBenchmarks', () => ({
  fetchProjectBenchmark: vi.fn(),
}));

describe('ProjectBenchmark', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(fetchProjectBenchmark).mockResolvedValue(benchmark);
  });

  it('renders cycle, budget, and overdue benchmark panels', async () => {
    const wrapper = mount(ProjectBenchmark, {
      global: { stubs },
      props: { projectId: 'project-1' },
    });
    await flushPromises();

    expect(fetchProjectBenchmark).toHaveBeenCalledWith('project-1');
    expect(wrapper.text()).toContain('周期');
    expect(wrapper.text()).toContain('预算偏差');
    expect(wrapper.text()).toContain('任务逾期');
    expect(wrapper.text()).toContain('P50');
    expect(wrapper.text()).toContain('30.00 天');

    vi.mocked(fetchProjectBenchmark).mockResolvedValue({
      ...benchmark,
      metrics: benchmark.metrics.map((metric) => ({
        ...metric,
        average: null,
        p50: null,
        p90: null,
      })),
      sample_count: 2,
      status: 'insufficient_sample',
    });
    await wrapper.find('[data-test="benchmark-project-id"]').setValue('project-2');
    await wrapper.find('[data-test="run-benchmark"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('样本不足');
  });
});

const benchmark = {
  metrics: [
    {
      average: 30,
      current_value: 15,
      key: 'cycle_days',
      label: '周期',
      p50: 30,
      p90: 46,
      sample_count: 5,
      unit: '天',
    },
    {
      average: 12,
      current_value: 20,
      key: 'budget_variance_percent',
      label: '预算偏差',
      p50: 10,
      p90: 30,
      sample_count: 5,
      unit: '%',
    },
    {
      average: 8,
      current_value: 10,
      key: 'task_overdue_rate',
      label: '任务逾期',
      p50: 5,
      p90: 18,
      sample_count: 5,
      unit: '%',
    },
  ],
  project_id: 'project-1',
  sample_count: 5,
  scope: {
    category_id: null,
    dept_id: 'dept-1',
    project_type_id: 'type-1',
    tag_ids: [],
  },
  status: 'ready' as const,
};

const stubs = {
  ElAlert: { props: ['title'], template: '<div>{{ title }}</div>' },
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
  ElSkeleton: { template: '<div><slot /></div>' },
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
};
