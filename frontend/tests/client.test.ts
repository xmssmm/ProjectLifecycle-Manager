import { describe, expect, it } from 'vitest';

import { apiClient } from '../src/api/client';

describe('apiClient', () => {
  it('uses the configured API base URL and timeout', () => {
    expect(apiClient.defaults.baseURL).toBe('http://localhost:8000/api/v1');
    expect(apiClient.defaults.timeout).toBe(15000);
  });
});
