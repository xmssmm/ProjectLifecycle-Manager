import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createAcceptanceStep,
  listAcceptanceSteps,
  updateAcceptanceStep,
} from '@/api/acceptanceSteps';
import { listDocuments } from '@/api/documents';
import { getPhase, listPhases } from '@/api/phases';
import type { AcceptanceStepRead } from '@/types/acceptanceSteps';
import type { DocumentRead } from '@/types/documents';
import type { PhaseDetailRead, PhaseRead } from '@/types/phases';
import PhaseDocumentPanel from '@/components/phase/PhaseDocumentPanel.vue';

vi.mock('@/api/acceptanceSteps', () => ({
  createAcceptanceStep: vi.fn(),
  listAcceptanceSteps: vi.fn(),
  updateAcceptanceStep: vi.fn(),
}));

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
    vi.mocked(listAcceptanceSteps).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(createAcceptanceStep).mockResolvedValue(createdAcceptanceStep);
    vi.mocked(updateAcceptanceStep).mockResolvedValue(completedAcceptanceStep);
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

  it('manages acceptance steps on phase 4 and links uploads to each step', async () => {
    vi.mocked(listPhases).mockResolvedValue({
      items: [phaseOne, phaseTwo, phaseFour],
      total: 3,
    });
    vi.mocked(getPhase).mockImplementation(async (phaseId: string) =>
      phaseId === 'phase-4' ? phaseFourDetail : phaseTwoDetail,
    );
    vi.mocked(listAcceptanceSteps).mockResolvedValue({
      items: [existingAcceptanceStep],
      total: 1,
    });

    const wrapper = mount(PhaseDocumentPanel, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    await wrapper.find('[data-test="select-doc-phase-phase-4"]').trigger('click');
    await flushPromises();

    expect(listAcceptanceSteps).toHaveBeenCalledWith('phase-4');
    expect(wrapper.text()).toContain('site acceptance');
    expect(wrapper.find('[data-test="upload-step-step-1"]').exists()).toBe(true);

    await wrapper.find('[data-test="acceptance-step-no"]').setValue('2');
    await wrapper.find('[data-test="acceptance-step-name"]').setValue('final review');
    await wrapper.find('[data-test="acceptance-step-responsible"]').setValue('user-3');
    await wrapper.find('[data-test="acceptance-step-plan-date"]').setValue('2026-05-21');
    await wrapper.find('[data-test="acceptance-step-description"]').setValue('final acceptance');
    await wrapper.find('[data-test="create-acceptance-step"]').trigger('click');
    await flushPromises();

    expect(createAcceptanceStep).toHaveBeenCalledWith('phase-4', {
      description: 'final acceptance',
      planDate: '2026-05-21',
      responsibleId: 'user-3',
      stepName: 'final review',
      stepNo: 2,
    });

    await wrapper.find('[data-test="complete-acceptance-step-step-1"]').trigger('click');
    await flushPromises();

    expect(updateAcceptanceStep).toHaveBeenCalledWith('phase-4', 'step-1', {
      status: 'completed',
    });
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

const phaseFour: PhaseRead = {
  ...phaseOne,
  code: 'acceptance',
  finish_at: null,
  id: 'phase-4',
  name: '验收',
  phase_no: 4,
  status: 'waiting',
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

const phaseFourDetail: PhaseDetailRead = {
  ...phaseFour,
  completion: {
    missing_doc_types: ['acceptance_report'],
    required_total: 1,
    uploaded_total: 0,
  },
  required_documents: [
    {
      doc_type: 'acceptance_report',
      procurement_type: null,
      qty_rule: '>=1',
      requirement: 'required',
    },
  ],
  uploaded_documents: [],
};

const existingAcceptanceStep: AcceptanceStepRead = {
  completed_at: null,
  created_at: '2026-05-10T00:00:00Z',
  description: 'site acceptance',
  id: 'step-1',
  phase_id: 'phase-4',
  plan_date: '2026-05-20',
  responsible_id: 'user-2',
  status: 'in_progress',
  step_name: 'site acceptance',
  step_no: 1,
  updated_at: '2026-05-10T00:00:00Z',
};

const createdAcceptanceStep: AcceptanceStepRead = {
  ...existingAcceptanceStep,
  id: 'step-2',
  plan_date: '2026-05-21',
  responsible_id: 'user-3',
  step_name: 'final review',
  step_no: 2,
};

const completedAcceptanceStep: AcceptanceStepRead = {
  ...existingAcceptanceStep,
  completed_at: '2026-05-22T00:00:00Z',
  status: 'completed',
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
    props: ['acceptanceStepId', 'docType'],
    template:
      '<button type="button" :data-test="acceptanceStepId ? `upload-step-${acceptanceStepId}` : `upload-${docType}`" @click="$emit(\'uploaded\', {})">upload</button>',
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
