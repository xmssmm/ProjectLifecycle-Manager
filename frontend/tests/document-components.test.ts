import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import { uploadDocument } from '@/api/documents';
import DocumentList from '@/components/document/DocumentList.vue';
import DocumentUploader from '@/components/document/DocumentUploader.vue';
import type { DocumentRead } from '@/types/documents';

vi.mock('@/api/documents', () => ({
  uploadDocument: vi.fn(),
}));

describe('DocumentUploader', () => {
  it('prevalidates the 50MB limit before uploading', async () => {
    const wrapper = mount(DocumentUploader, {
      global: { stubs },
      props: {
        docType: 'contract',
        phaseId: 'phase-1',
        subProjectId: 'sub-1',
      },
    });
    const oversized = new File(['tiny'], 'large.pdf', { type: 'application/pdf' });
    Object.defineProperty(oversized, 'size', { value: 51 * 1024 * 1024 });

    await wrapper.find('[data-test="document-drop-zone"]').trigger('drop', {
      dataTransfer: { files: [oversized] },
    });

    expect(uploadDocument).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('50MB');
  });

  it('shows backend rejection reason and retries the last failed file', async () => {
    vi.mocked(uploadDocument)
      .mockImplementationOnce(async (_payload, _client, onProgress) => {
        onProgress?.(35);
        throw {
          response: {
            data: {
              data: { rejection_reason: 'blacklisted extension' },
              message: 'Upload rejected',
            },
          },
        };
      })
      .mockResolvedValueOnce(sampleDocuments[0]);
    const wrapper = mount(DocumentUploader, {
      global: { stubs },
      props: {
        docType: 'contract',
        phaseId: 'phase-1',
        subProjectId: 'sub-1',
      },
    });

    await wrapper.find('[data-test="document-drop-zone"]').trigger('drop', {
      dataTransfer: {
        files: [new File(['pdf'], 'contract.pdf', { type: 'application/pdf' })],
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('blacklisted extension');
    expect(wrapper.text()).toContain('35%');

    await wrapper.find('[data-test="retry-upload"]').trigger('click');
    await flushPromises();

    expect(uploadDocument).toHaveBeenCalledTimes(2);
    expect(wrapper.emitted('uploaded')?.[0]).toEqual([sampleDocuments[0]]);
  });
});

describe('DocumentList', () => {
  it('groups documents by type and switches to historical versions', async () => {
    const wrapper = mount(DocumentList, {
      global: { stubs },
      props: {
        documents: sampleDocuments,
      },
    });

    expect(wrapper.text()).toContain('contract');
    expect(wrapper.text()).toContain('contract-v2.pdf');
    expect(wrapper.text()).toContain('meeting-v1.pdf');

    await wrapper.find('[data-test="show-history-contract"]').trigger('click');
    await wrapper.find('[data-test="select-contract-v1"]').trigger('click');

    expect(wrapper.text()).toContain('contract-v1.pdf');
    expect(wrapper.text()).toContain('v1');
    expect(wrapper.text()).toContain('v2');
  });
});

const sampleDocuments: DocumentRead[] = [
  {
    acceptance_step_id: null,
    created_at: '2026-05-10T02:00:00Z',
    doc_no: 'DOC-2',
    doc_type: 'contract',
    file_name: 'contract-v2.pdf',
    file_size: 2048,
    id: 'doc-2',
    is_deleted: false,
    is_latest: true,
    phase_id: 'phase-1',
    sub_project_id: 'sub-1',
    updated_at: '2026-05-10T02:00:00Z',
    uploader_id: 'user-2',
    version: 2,
  },
  {
    acceptance_step_id: null,
    created_at: '2026-05-10T01:00:00Z',
    doc_no: 'DOC-1',
    doc_type: 'contract',
    file_name: 'contract-v1.pdf',
    file_size: 1024,
    id: 'doc-1',
    is_deleted: false,
    is_latest: false,
    phase_id: 'phase-1',
    sub_project_id: 'sub-1',
    updated_at: '2026-05-10T01:00:00Z',
    uploader_id: 'user-1',
    version: 1,
  },
  {
    acceptance_step_id: null,
    created_at: '2026-05-10T03:00:00Z',
    doc_no: 'DOC-3',
    doc_type: 'meeting_minutes',
    file_name: 'meeting-v1.pdf',
    file_size: 512,
    id: 'doc-3',
    is_deleted: false,
    is_latest: true,
    phase_id: 'phase-1',
    sub_project_id: 'sub-1',
    updated_at: '2026-05-10T03:00:00Z',
    uploader_id: 'user-3',
    version: 1,
  },
];

const stubs = {
  ElAlert: {
    props: ['description', 'title'],
    template: '<section>{{ title }}{{ description }}</section>',
  },
  ElButton: {
    props: ['disabled', 'icon', 'loading', 'type'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElProgress: { props: ['percentage'], template: '<span>{{ percentage }}%</span>' },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
};
