import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { askAnalyticsQuestion } from '@/api/analyticsQa';
import type { AnalyticsQaAnswerRead } from '@/api/analyticsQa';
import AnalyticsQuestionAnswer from '@/views/analytics/AnalyticsQuestionAnswer.vue';

vi.mock('@/api/analyticsQa', () => ({
  askAnalyticsQuestion: vi.fn(),
}));

describe('AnalyticsQuestionAnswer', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(askAnalyticsQuestion).mockResolvedValue(answer);
  });

  it('renders answer, cited table rows, and chart suggestion', async () => {
    const wrapper = mount(AnalyticsQuestionAnswer, { global: { stubs } });

    await wrapper.find('[data-test="analytics-question"]').setValue('本部门今年项目数');
    await wrapper.find('[data-test="ask-analytics-question"]').trigger('click');
    await flushPromises();

    expect(askAnalyticsQuestion).toHaveBeenCalledWith('本部门今年项目数');
    expect(wrapper.text()).toContain('本部门今年项目数为 3 个。');
    expect(wrapper.text()).toContain('project_count');
    expect(wrapper.text()).toContain('3');
    expect(wrapper.text()).toContain('stat');
  });
});

const answer: AnalyticsQaAnswerRead = {
  answer: '本部门今年项目数为 3 个。',
  chart: {
    type: 'stat',
    x_field: null,
    y_field: 'project_count',
  },
  columns: [
    {
      aggregates: ['count'],
      filter_ops: [],
      key: 'project_count',
      label: 'project_count',
      type: 'number',
    },
  ],
  query_config: {
    dataset: 'project_overview',
    dimensions: [],
    filters: [],
    limit: 1,
    metrics: [{ aggregate: 'count', alias: 'project_count', field: 'id' }],
    sort: [],
  },
  question: '本部门今年项目数',
  row_count: 1,
  rows: [{ project_count: 3 }],
  source: 'rules',
};

const stubs = {
  ElButton: {
    props: ['disabled', 'loading'],
    template:
      '<button type="button" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
};
