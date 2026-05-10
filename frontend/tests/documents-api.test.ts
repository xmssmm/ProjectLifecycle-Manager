import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import { downloadDocument, listDocuments, uploadDocument } from '../src/api/documents';

describe('documents api', () => {
  it('supports listing, multipart upload, and download endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: { items: [sampleDocument], total: 1 },
    });

    await listDocuments(
      {
        docType: 'contract',
        includeHistory: true,
        phaseId: 'phase-1',
        subProjectId: 'sub-1',
      },
      client,
    );

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleDocument,
    });
    await uploadDocument(
      {
        docType: 'contract',
        file: new File(['pdf'], 'contract.pdf', { type: 'application/pdf' }),
        phaseId: 'phase-1',
        subProjectId: 'sub-1',
      },
      client,
    );

    client.defaults.adapter = recordingAdapter(calls, new Blob(['pdf']));
    await downloadDocument('doc-1', client);

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: {
        doc_type: 'contract',
        include_history: true,
        phase_id: 'phase-1',
        sub_project_id: 'sub-1',
      },
      url: '/documents',
    });
    expect(calls[1]).toMatchObject({ method: 'post', url: '/documents' });
    expect(calls[1].data).toBeInstanceOf(FormData);
    expect(calls[2]).toMatchObject({
      method: 'get',
      responseType: 'blob',
      url: '/documents/doc-1/download',
    });
  });
});

const sampleDocument = {
  acceptance_step_id: null,
  created_at: '2026-05-10T00:00:00Z',
  doc_no: 'DOC-1',
  doc_type: 'contract',
  file_name: 'contract.pdf',
  file_size: 512,
  id: 'doc-1',
  is_deleted: false,
  is_latest: true,
  phase_id: 'phase-1',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T00:00:00Z',
  uploader_id: 'user-1',
  version: 2,
};

function recordingAdapter(calls: AxiosRequestConfig[], data: unknown): AxiosAdapter {
  return async (config) => {
    calls.push(config);
    return {
      config,
      data,
      headers: {},
      status: 200,
      statusText: 'OK',
    };
  };
}
