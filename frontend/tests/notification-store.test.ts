import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getUnreadNotificationCount,
  listNotifications,
  listNotificationPreferences,
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreferences,
} from '@/api/notifications';
import { useNotificationStore } from '@/stores/useNotificationStore';
import type { NotificationPreferenceRead, NotificationRead } from '@/types/notifications';

vi.mock('@/api/notifications', () => ({
  getUnreadNotificationCount: vi.fn(),
  listNotifications: vi.fn(),
  listNotificationPreferences: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}));

describe('notification store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads notifications and keeps unread count in sync after read actions', async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [unreadNotification, readNotification],
      page: 1,
      page_size: 10,
      total: 2,
    });
    vi.mocked(getUnreadNotificationCount).mockResolvedValue({ count: 1 });
    vi.mocked(markNotificationRead).mockResolvedValue({
      ...unreadNotification,
      read_at: '2026-05-10T01:00:00Z',
    });
    vi.mocked(markAllNotificationsRead).mockResolvedValue({ read_count: 1 });
    const store = useNotificationStore();

    await store.fetchNotifications({ page: 1, pageSize: 10, unread: false });
    await store.fetchUnreadCount();
    await store.markRead('notif-1');
    await store.markAllRead();

    expect(listNotifications).toHaveBeenCalledWith({
      page: 1,
      pageSize: 10,
      unread: false,
    });
    expect(getUnreadNotificationCount).toHaveBeenCalled();
    expect(markNotificationRead).toHaveBeenCalledWith('notif-1');
    expect(markAllNotificationsRead).toHaveBeenCalled();
    expect(store.notifications.every((notification) => notification.read_at !== null)).toBe(true);
    expect(store.unreadCount).toBe(0);
  });

  it('loads and saves notification preferences', async () => {
    vi.mocked(listNotificationPreferences).mockResolvedValue({ items: [taskPreference] });
    vi.mocked(updateNotificationPreferences).mockResolvedValue({
      items: [{ ...taskPreference, enabled: false }],
    });
    const store = useNotificationStore();

    await store.fetchPreferences();
    await store.savePreferences([{ scenario: 'task_assigned', enabled: false }]);

    expect(listNotificationPreferences).toHaveBeenCalled();
    expect(updateNotificationPreferences).toHaveBeenCalledWith({
      preferences: [{ enabled: false, scenario: 'task_assigned' }],
    });
    expect(store.preferences).toEqual([{ ...taskPreference, enabled: false }]);
  });
});

const unreadNotification: NotificationRead = {
  created_at: '2026-05-10T00:00:00Z',
  dedup_key: 'task_assigned:user-1:task-1:20260510',
  id: 'notif-1',
  payload: { task_id: 'task-1', task_no: 'Z-001-T-001' },
  read_at: null,
  receiver_id: 'user-1',
  scenario: 'task_assigned',
  source_id: 'task-1',
  updated_at: '2026-05-10T00:00:00Z',
};

const readNotification: NotificationRead = {
  ...unreadNotification,
  id: 'notif-2',
  read_at: '2026-05-09T01:00:00Z',
};

const taskPreference: NotificationPreferenceRead = {
  description: '任务执行人收到任务分配提醒',
  direct_related: true,
  enabled: true,
  label: '任务分配',
  scenario: 'task_assigned',
};
