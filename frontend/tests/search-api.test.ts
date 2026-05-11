import { describe, expect, it, vi } from 'vitest';

import { searchDocuments } from '@/api/search';

describe('search api', () => {
  it('maps document search to backend route', async () => {
    const client = {
      get: vi.fn(() => Promise.resolve({ data: { data: results } })),
    };

    await expect(searchDocuments({ q: 'budget', scope: 'documents' }, client as never)).resolves.toEqual(
      results,
    );

    expect(client.get).toHaveBeenCalledWith('/search', {
      params: { q: 'budget', scope: 'documents' },
    });
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
