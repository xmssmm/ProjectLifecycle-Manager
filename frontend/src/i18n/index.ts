import { createI18n } from 'vue-i18n';

import enUS from './locales/en-US';
import zhCN from './locales/zh-CN';

export const DEFAULT_LOCALE = 'zh-CN';
export const LOCALE_STORAGE_KEY = 'management.locale';

export type SupportedLocale = 'zh-CN' | 'en-US';
export type StatusTagType = 'danger' | 'info' | 'primary' | 'success' | 'warning';

export interface LocaleOption {
  label: string;
  value: SupportedLocale;
}

export interface StatusMeta {
  label: string;
  type: StatusTagType;
}

export const messages = {
  'en-US': enUS,
  'zh-CN': zhCN,
} as const;

export const i18n = createI18n({
  fallbackLocale: DEFAULT_LOCALE,
  legacy: false,
  locale: resolveInitialLocale(),
  messages,
});

export const localeOptions: LocaleOption[] = [
  { label: zhCN.locale.zhCN, value: 'zh-CN' },
  { label: zhCN.locale.enUS, value: 'en-US' },
];

const statusTypes: Record<string, StatusTagType> = {
  active: 'success',
  approved: 'success',
  archived: 'info',
  candidate_rejected: 'danger',
  closed: 'info',
  completed: 'success',
  disabled: 'info',
  draft: 'info',
  failed: 'danger',
  forced: 'warning',
  in_progress: 'primary',
  not_started: 'info',
  overdue: 'danger',
  pending: 'warning',
  pending_candidate: 'warning',
  password_reset_required: 'warning',
  pending_review: 'warning',
  queued: 'info',
  rejected: 'danger',
  review_rejected: 'danger',
  reviewing: 'primary',
  revoked: 'warning',
  running: 'primary',
  submitted: 'primary',
  terminated: 'danger',
  waiting: 'info',
};

setDocumentLocale(getCurrentLocale());

export function getCurrentLocale(): SupportedLocale {
  return i18n.global.locale.value as SupportedLocale;
}

export function setLocale(locale: SupportedLocale): void {
  i18n.global.locale.value = locale;
  setStorageLocale(locale);
  setDocumentLocale(locale);
}

export function t(key: string): string {
  void i18n.global.locale.value;
  return i18n.global.t(key);
}

export function getStatusMeta(status: string): StatusMeta {
  const key = `status.${status}`;
  const label = i18n.global.te(key) ? t(key) : status;
  return {
    label,
    type: statusTypes[status] ?? 'info',
  };
}

function resolveInitialLocale(): SupportedLocale {
  const storedLocale = getStorageLocale();
  return storedLocale ?? DEFAULT_LOCALE;
}

function getStorageLocale(): SupportedLocale | null {
  if (!hasBrowserStorage()) {
    return null;
  }
  const value = globalThis.localStorage.getItem(LOCALE_STORAGE_KEY);
  return isSupportedLocale(value) ? value : null;
}

function setStorageLocale(locale: SupportedLocale): void {
  if (hasBrowserStorage()) {
    globalThis.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  }
}

function setDocumentLocale(locale: SupportedLocale): void {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale;
  }
}

function hasBrowserStorage(): boolean {
  return typeof globalThis.localStorage !== 'undefined';
}

function isSupportedLocale(value: unknown): value is SupportedLocale {
  return value === 'zh-CN' || value === 'en-US';
}
