export const DEFAULT_USER_TIMEZONE = 'Asia/Shanghai';

const dateTimeFormatterOptions: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  hour: '2-digit',
  hour12: false,
  minute: '2-digit',
  month: '2-digit',
  year: 'numeric',
};

export function normalizeUserTimezone(timezone: string | null | undefined): string {
  if (!timezone) {
    return DEFAULT_USER_TIMEZONE;
  }
  try {
    new Intl.DateTimeFormat('zh-CN', { timeZone: timezone }).format(new Date(0));
    return timezone;
  } catch {
    return DEFAULT_USER_TIMEZONE;
  }
}

export function formatUserDateTime(
  value: Date | number | string | null | undefined,
  timezone: string | null | undefined,
): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '-';
  }

  const formatter = new Intl.DateTimeFormat('zh-CN', {
    ...dateTimeFormatterOptions,
    timeZone: normalizeUserTimezone(timezone),
  });
  const parts = Object.fromEntries(
    formatter.formatToParts(date).map((part) => [part.type, part.value]),
  );
  return `${parts.year}/${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
}
