import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { searchDocuments } from '@/api/search';
import SearchView from '@/views/SearchView.vue';

vi.mock('@/api/search', () => ({
  searchDocuments: vi.fn(),
}));

describe('SearchView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(searchDocuments).mockResolvedValue(results);
  });

  it('searches documents and renders result context', async () => {
    const wrapper = mount(SearchView, { global: { stubs } });

    await wrapper.find('[data-test="search-query"]').setValue('budget');
    await wrapper.find('[data-test="submit-search"]').trigger('click');
    await flushPromises();

    expect(searchDocuments).toHaveBeenCalledWith({ q: 'budget', scope: 'documents' });
    expect(wrapper.text()).toContain('meeting.txt');
    expect(wrapper.text()).toContain('Z-2026-0001-ZX-001');
    expect(wrapper.text()).toContain('budget approval milestone');
  });
});

const results = {
  items: [
    {
      doc_type: 'meeting_material',
      document_id: 'doc-1',
      file_name: 'meeting.txt',
      phase_id: 'phase-1',
      phase_name: '立项',
      snippet: 'budget approval milestone',
      sub_project_id: 'sub-1',
      sub_project_name: '子项目',
      sub_project_no: 'Z-2026-0001-ZX-001',
    },
  ],
  total: 1,
};

const stubs = {
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElTag: { template: '<span><slot /></span>' },
};
