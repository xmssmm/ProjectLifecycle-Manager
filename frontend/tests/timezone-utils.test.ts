import { describe, expect, it } from 'vitest';

import { formatUserDateTime } from '../src/utils/timezone';

describe('timezone utils', () => {
  it('formats the same UTC instant in the selected user timezone', () => {
    const value = '2026-05-11T01:00:00Z';

    expect(formatUserDateTime(value, 'Asia/Shanghai')).toContain('2026/05/11 09:00');
    expect(formatUserDateTime(value, 'America/New_York')).toContain('2026/05/10 21:00');
  });

  it('falls back to Asia/Shanghai for empty or invalid timezone values', () => {
    const value = '2026-05-11T01:00:00Z';

    expect(formatUserDateTime(value, '')).toContain('2026/05/11 09:00');
    expect(formatUserDateTime(value, 'Mars/Base')).toContain('2026/05/11 09:00');
  });
});
