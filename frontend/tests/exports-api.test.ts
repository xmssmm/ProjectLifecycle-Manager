import { describe, expect, it, vi } from 'vitest';

import {
  createDatabaseExportJob,
  downloadDatabaseExport,
  getDatabaseExportJob,
} from '@/api/exports';

describe('exports api', () => {
  it('maps database export job and download endpoints', async () => {
    const job = { id: 'job-1', status: 'completed' };
    const blob = new Blob(['zip']);
    const client = {
      get: vi.fn((url: string) => {
        if (url.endsWith('/download')) {
          return Promise.resolve({ data: blob });
        }
        return Promise.resolve({ data: { data: job } });
      }),
      post: vi.fn(() => Promise.resolve({ data: { data: job } })),
    };

    await expect(createDatabaseExportJob(client as never)).resolves.toEqual(job);
    await expect(getDatabaseExportJob('job-1', client as never)).resolves.toEqual(job);
    await expect(downloadDatabaseExport('job-1', client as never)).resolves.toBe(blob);

    expect(client.post).toHaveBeenCalledWith('/exports/database');
    expect(client.get).toHaveBeenCalledWith('/exports/database/job-1');
    expect(client.get).toHaveBeenCalledWith('/exports/database/job-1/download', {
      responseType: 'blob',
    });
  });
});
