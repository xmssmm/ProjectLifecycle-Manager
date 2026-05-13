import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import DocumentList from '@/components/document/DocumentList.vue';

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(),
}));

vi.mock('pdfjs-dist/build/pdf.worker.mjs?url', () => ({ default: 'worker-url' }));

describe('DocumentList', () => {
  it('uses display_name as the primary file title', () => {
    const wrapper = mount(DocumentList, {
      props: {
        documents: [
          {
            acceptance_step_id: null,
            created_at: '2026-05-13T09:00:00+08:00',
            display_name: 'Main Contract Scan',
            doc_no: 'D001',
            doc_type: 'contract',
            file_name: 'uuid-contract.pdf',
            file_size: 123,
            id: 'doc-1',
            is_deleted: false,
            is_latest: true,
            phase_id: 'phase-1',
            scan_result: null,
            scan_status: 'clean',
            scanned_at: null,
            sub_project_id: 'sub-1',
            updated_at: '',
            uploader_id: 'user-1',
            version: 1,
          },
        ],
      },
      global: {
        stubs: {
          Component: true,
          ElEmpty: true,
          ElTag: true,
          PdfPreview: true,
        },
      },
    });

    expect(wrapper.text()).toContain('Main Contract Scan');
    expect(wrapper.text()).not.toContain('uuid-contract.pdfv1');
  });
});
