import { describe, expect, it, vi } from 'vitest';

import { downloadProjectImportTemplate, importProjectWorkbook } from '@/api/imports';

describe('imports api', () => {
  it('maps project import template and upload endpoints', async () => {
    const blob = new Blob(['template']);
    const result = { batch_no: 'IMPORT-20260511-ABCDEF12' };
    const post = vi.fn((url: string, body: FormData) => {
      void url;
      void body;
      return Promise.resolve({ data: { data: result } });
    });
    const client = {
      get: vi.fn(() => Promise.resolve({ data: blob })),
      post,
    };
    const file = new File(['xlsx'], 'projects.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    await expect(downloadProjectImportTemplate(client as never)).resolves.toBe(blob);
    await expect(importProjectWorkbook(file, client as never)).resolves.toEqual(result);

    expect(client.get).toHaveBeenCalledWith('/imports/projects/template', {
      responseType: 'blob',
    });
    expect(client.post).toHaveBeenCalledWith('/imports/projects', expect.any(FormData));
    const uploadCall = post.mock.calls[0] as [string, FormData];
    expect(uploadCall[1].get('file')).toBe(file);
  });
});
