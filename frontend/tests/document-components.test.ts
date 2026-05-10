import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { previewDocument, previewOfficeDocument, uploadDocument } from '@/api/documents';
import DocumentList from '@/components/document/DocumentList.vue';
import PdfPreview from '@/components/document/PdfPreview.vue';
import DocumentUploader from '@/components/document/DocumentUploader.vue';
import type { DocumentRead } from '@/types/documents';

vi.mock('@/api/documents', () => ({
  previewDocument: vi.fn(),
  previewOfficeDocument: vi.fn(),
  uploadDocument: vi.fn(),
}));

const pdfMocks = vi.hoisted(() => {
  const page = {
    getViewport: vi.fn((options: { scale: number }) => ({
      height: 900 * options.scale,
      width: 600 * options.scale,
    })),
    render: vi.fn(() => ({ promise: Promise.resolve() })),
  };
  return {
    document: {
      destroy: vi.fn(),
      getPage: vi.fn(async () => page),
      numPages: 3,
    },
    page,
  };
});

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(() => ({ promise: Promise.resolve(pdfMocks.document) })),
}));

vi.mock('pdfjs-dist/build/pdf.mjs', () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(() => ({ promise: Promise.resolve(pdfMocks.document) })),
}));

vi.mock('pdfjs-dist/build/pdf.worker.mjs?url', () => ({ default: 'worker-url' }));

beforeEach(() => {
  vi.clearAllMocks();
});

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

  it('shows preview only for PDF documents and opens the preview panel', async () => {
    const wrapper = mount(DocumentList, {
      global: {
        stubs: {
          ...stubs,
          PdfPreview: {
            props: ['document', 'modelValue'],
            template:
              '<section v-if="modelValue" data-test="pdf-preview">{{ document?.file_name }}</section>',
          },
        },
      },
      props: {
        documents: previewDocuments,
      },
    });

    expect(wrapper.find('[data-test="preview-contract"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="preview-meeting_minutes"]').exists()).toBe(false);

    await wrapper.find('[data-test="preview-contract"]').trigger('click');

    expect(wrapper.find('[data-test="pdf-preview"]').text()).toContain('contract-v2.pdf');
  });

  it('shows Office preview for all supported Office extensions', async () => {
    const wrapper = mount(DocumentList, {
      global: {
        stubs: {
          ...stubs,
          PdfPreview: {
            props: ['document', 'modelValue', 'previewLoader'],
            template:
              '<section v-if="modelValue" data-test="office-preview" @click="previewLoader(document.id)">{{ document?.file_name }}</section>',
          },
        },
      },
      props: {
        documents: officePreviewDocuments,
      },
    });

    for (const extension of ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']) {
      expect(wrapper.find(`[data-test="preview-office-office_${extension}"]`).exists()).toBe(true);
    }

    await wrapper.find('[data-test="preview-office-office_docx"]').trigger('click');
    await wrapper.find('[data-test="office-preview"]').trigger('click');

    expect(previewOfficeDocument).toHaveBeenCalledWith('office-docx');
  });

  it('shows scan status and disables access before a clean result', async () => {
    const wrapper = mount(DocumentList, {
      global: { stubs },
      props: {
        documents: [
          {
            ...sampleDocuments[0],
            doc_type: 'pending_contract',
            scan_status: 'pending',
          },
          {
            ...sampleDocuments[1],
            doc_type: 'infected_contract',
            scan_status: 'infected',
            scan_result: 'EICAR-Test-File FOUND',
          },
        ],
      },
    });

    expect(wrapper.find('[data-test="scan-status-pending_contract"]').text()).toContain('扫描中');
    expect(wrapper.find('[data-test="scan-status-infected_contract"]').text()).toContain('已隔离');
    expect(wrapper.find('[data-test="preview-pending_contract"]').attributes('disabled')).toBeDefined();
    expect(wrapper.find('[data-test="preview-infected_contract"]').attributes('disabled')).toBeDefined();
  });
});

describe('PdfPreview', () => {
  it('loads PDF preview, supports paging, zooming, and exposes download link', async () => {
    const getContext = vi
      .spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockImplementation(() => ({}) as CanvasRenderingContext2D);
    vi.mocked(previewDocument).mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));
    const wrapper = mount(PdfPreview, {
      global: { stubs },
      props: {
        document: sampleDocuments[0],
        loadPdf: async () => pdfMocks.document,
        modelValue: true,
      },
    });

    await flushPromises();

    expect(previewDocument).toHaveBeenCalledWith('doc-2');
    expect(wrapper.text()).toContain('1 / 3');
    expect(wrapper.text()).toContain('100%');

    await wrapper.find('[data-test="next-page"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('2 / 3');

    await wrapper.find('[data-test="zoom-in"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('125%');

    const download = wrapper.find('[data-test="preview-download"]');
    expect(download.attributes('download')).toBe('contract-v2.pdf');
    expect(download.attributes('href')).toContain('blob:');
    expect(wrapper.find('[data-test="pdf-preview-dialog"]').classes()).toContain(
      'pdf-preview--mobile-fullscreen',
    );
    getContext.mockRestore();
  });

  it('uses a custom preview loader and converted download filename', async () => {
    const getContext = vi
      .spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockImplementation(() => ({}) as CanvasRenderingContext2D);
    const previewLoader = vi.fn().mockResolvedValue(new Blob(['converted'], { type: 'application/pdf' }));
    const wrapper = mount(PdfPreview, {
      global: { stubs },
      props: {
        document: officePreviewDocuments[1],
        downloadFileName: 'sample.pdf',
        loadPdf: async () => pdfMocks.document,
        modelValue: true,
        previewLoader,
      },
    });

    await flushPromises();

    expect(previewLoader).toHaveBeenCalledWith('office-docx');
    expect(previewDocument).not.toHaveBeenCalled();
    expect(wrapper.find('[data-test="preview-download"]').attributes('download')).toBe(
      'sample.pdf',
    );
    getContext.mockRestore();
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
    scan_status: 'clean',
    scan_result: 'No threats found',
    scanned_at: '2026-05-10T02:01:00Z',
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
    scan_status: 'clean',
    scan_result: 'No threats found',
    scanned_at: '2026-05-10T01:01:00Z',
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
    scan_status: 'clean',
    scan_result: 'No threats found',
    scanned_at: '2026-05-10T03:01:00Z',
    sub_project_id: 'sub-1',
    updated_at: '2026-05-10T03:00:00Z',
    uploader_id: 'user-3',
    version: 1,
  },
];

const previewDocuments: DocumentRead[] = [
  sampleDocuments[0],
  {
    ...sampleDocuments[2],
    doc_type: 'meeting_minutes',
    file_name: 'meeting-v1.docx',
  },
];

const officePreviewDocuments: DocumentRead[] = (
  ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'] as const
).map((extension) => ({
  acceptance_step_id: null,
  created_at: '2026-05-10T04:00:00Z',
  doc_no: `OFFICE-${extension}`,
  doc_type: `office_${extension}`,
  file_name: `sample.${extension}`,
  file_size: 4096,
  id: `office-${extension}`,
  is_deleted: false,
  is_latest: true,
  phase_id: 'phase-1',
  scan_status: 'clean',
  scan_result: 'No threats found',
  scanned_at: '2026-05-10T04:01:00Z',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T04:00:00Z',
  uploader_id: 'user-office',
  version: 1,
}));

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
  ElDialog: {
    props: ['modelValue'],
    template:
      '<section v-if="modelValue"><slot name="header" /><slot /><slot name="footer" /></section>',
  },
  ElProgress: { props: ['percentage'], template: '<span>{{ percentage }}%</span>' },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
};
