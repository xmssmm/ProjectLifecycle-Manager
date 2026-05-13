import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  confirmDocumentType,
  suggestDocumentType,
  type DocumentClassificationRead,
} from '@/api/documentClassification';
import { uploadDocument } from '@/api/documents';
import DocumentUploader from '@/components/document/DocumentUploader.vue';
import type { DocumentRead } from '@/types/documents';

vi.mock('@/api/documents', () => ({
  uploadDocument: vi.fn(),
}));

vi.mock('@/api/documentClassification', () => ({
  confirmDocumentType: vi.fn(),
  suggestDocumentType: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DocumentUploader document classification', () => {
  it('pauses upload until the user confirms a suggested document type', async () => {
    vi.mocked(suggestDocumentType).mockResolvedValue(
      classificationResult({
        doc_type: 'contract',
        reason: '文件名包含「合同」',
      }),
    );
    vi.mocked(uploadDocument).mockResolvedValue({ ...sampleDocument, doc_type: 'contract' });
    vi.mocked(confirmDocumentType).mockResolvedValue({ ...sampleDocument, doc_type: 'contract' });
    const wrapper = mountUploader();

    await wrapper.find('[data-test="document-drop-zone"]').trigger('drop', {
      dataTransfer: {
        files: [new File(['pdf'], '采购合同.pdf', { type: 'application/pdf' })],
      },
    });
    await flushPromises();

    expect(uploadDocument).not.toHaveBeenCalled();
    expect(wrapper.find('[data-test="document-type-suggestion"]').text()).toContain('contract');

    await wrapper.find('[data-test="confirm-document-type"]').trigger('click');
    await flushPromises();

    expect(uploadDocument).toHaveBeenCalledWith(
      expect.objectContaining({ docType: 'contract' }),
      undefined,
      expect.any(Function),
    );
    expect(confirmDocumentType).toHaveBeenCalledWith('doc-1', 'contract');
  });

  it('keeps the original upload type when the suggestion is ignored', async () => {
    vi.mocked(suggestDocumentType).mockResolvedValue(
      classificationResult({
        doc_type: 'contract',
        reason: '文件名包含「合同」',
      }),
    );
    vi.mocked(uploadDocument).mockResolvedValue(sampleDocument);
    const wrapper = mountUploader();

    await wrapper.find('[data-test="document-drop-zone"]').trigger('drop', {
      dataTransfer: {
        files: [new File(['pdf'], '采购合同.pdf', { type: 'application/pdf' })],
      },
    });
    await flushPromises();
    await wrapper.find('[data-test="ignore-document-type"]').trigger('click');
    await flushPromises();

    expect(uploadDocument).toHaveBeenCalledWith(
      expect.objectContaining({ docType: 'meeting_material' }),
      undefined,
      expect.any(Function),
    );
    expect(confirmDocumentType).not.toHaveBeenCalled();
  });
});

function mountUploader() {
  return mount(DocumentUploader, {
    global: { stubs },
    props: {
      docType: 'meeting_material',
      phaseId: 'phase-1',
      subProjectId: 'sub-1',
    },
  });
}

function classificationResult(
  suggestion: Pick<DocumentClassificationRead['suggestions'][number], 'doc_type' | 'reason'>,
): DocumentClassificationRead {
  return {
    current_doc_type: 'meeting_material',
    document_id: null,
    file_name: '采购合同.pdf',
    phase_id: 'phase-1',
    sub_project_id: 'sub-1',
    suggestions: [
      {
        confidence: 0.9,
        source: 'rules',
        ...suggestion,
      },
    ],
  };
}

const sampleDocument: DocumentRead = {
  acceptance_step_id: null,
  created_at: '2026-05-10T02:00:00Z',
  display_name: '采购合同.pdf',
  doc_no: 'DOC-1',
  doc_type: 'meeting_material',
  file_name: '采购合同.pdf',
  file_size: 2048,
  id: 'doc-1',
  is_deleted: false,
  is_latest: true,
  phase_id: 'phase-1',
  scan_result: null,
  scan_status: 'clean',
  scanned_at: null,
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T02:00:00Z',
  uploader_id: 'user-1',
  version: 1,
};

const stubs = {
  ElAlert: {
    props: ['description', 'title'],
    template: '<section>{{ title }}{{ description }}</section>',
  },
  ElInput: {
    props: ['modelValue', 'placeholder'],
    template: '<input :value="modelValue" :placeholder="placeholder" />',
  },
  ElProgress: { props: ['percentage'], template: '<span>{{ percentage }}%</span>' },
};
