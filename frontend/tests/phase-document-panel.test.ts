import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listDocuments } from '@/api/documents';
import { getPhase, listPhases } from '@/api/phases';
import type { DocumentRead } from '@/types/documents';
import type { PhaseDetailRead, PhaseRead } from '@/types/phases';
import PhaseDocumentPanel from '@/components/phase/PhaseDocumentPanel.vue';

vi.mock('@/api/documents', () => ({
  downloadDocument: vi.fn(),
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
}));

vi.mock('@/api/phases', () => ({
  getPhase: vi.fn(),
  listPhases: vi.fn(),
  promotePhase: vi.fn(),
}));

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(),
}));

vi.mock('pdfjs-dist/build/pdf.worker.mjs?url', () => ({ default: 'worker-url' }));

describe('PhaseDocumentPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listPhases).mockResolvedValue({ items: [phaseOne, phaseTwo], total: 2 });
    vi.mocked(getPhase).mockResolvedValue(phaseTwoDetail);
    vi.mocked(listDocuments).mockResolvedValue({ items: [uploadedDocument], total: 1 });
  });

  it('highlights missing required documents and refreshes after upload', async () => {
    const wrapper = mount(PhaseDocumentPanel, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    expect(getPhase).toHaveBeenCalledWith('phase-2');
    expect(listDocuments).toHaveBeenCalledWith({
      includeHistory: true,
      phaseId: 'phase-2',
      subProjectId: 'sub-1',
    });
    expect(wrapper.find('[data-test="missing-doc-contract"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('contract');
    expect(wrapper.find('[data-test="document-list"]').text()).toContain('1');

    await wrapper.find('[data-test="upload-contract"]').trigger('click');
    await flushPromises();

    expect(getPhase).toHaveBeenCalledTimes(2);
    expect(listDocuments).toHaveBeenCalledTimes(2);
  });
});

const phaseOne: PhaseRead = {
  code: 'init',
  created_at: '2026-05-10T00:00:00Z',
  enter_at: '2026-05-10T00:00:00Z',
  finish_at: '2026-05-11T00:00:00Z',
  id: 'phase-1',
  name: '立项',
  phase_no: 1,
  procurement_type: null,
  status: 'completed',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-11T00:00:00Z',
};

const phaseTwo: PhaseRead = {
  ...phaseOne,
  code: 'contract',
  finish_at: null,
  id: 'phase-2',
  name: '合同签订',
  phase_no: 2,
  status: 'in_progress',
};

const phaseTwoDetail: PhaseDetailRead = {
  ...phaseTwo,
  completion: {
    missing_doc_types: ['contract'],
    required_total: 2,
    uploaded_total: 1,
  },
  required_documents: [
    {
      doc_type: 'contract',
      procurement_type: null,
      qty_rule: '>=1',
      requirement: 'required',
    },
    {
      doc_type: 'acceptance_proof',
      procurement_type: null,
      qty_rule: '>=1',
      requirement: 'required',
    },
  ],
  uploaded_documents: [],
};

const uploadedDocument: DocumentRead = {
  acceptance_step_id: null,
  created_at: '2026-05-10T02:00:00Z',
  doc_no: 'DOC-1',
  doc_type: 'acceptance_proof',
  file_name: 'proof.pdf',
  file_size: 2048,
  id: 'doc-1',
  is_deleted: false,
  is_latest: true,
  phase_id: 'phase-2',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T02:00:00Z',
  uploader_id: 'user-1',
  version: 1,
};

const stubs = {
  DocumentList: {
    props: ['documents'],
    template: '<section data-test="document-list">{{ documents.length }}</section>',
  },
  DocumentUploader: {
    props: ['docType'],
    template:
      '<button type="button" :data-test="`upload-${docType}`" @click="$emit(\'uploaded\', {})">upload</button>',
  },
  ElButton: {
    emits: ['click'],
    props: ['type'],
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElSkeleton: { template: '<section />' },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
};
