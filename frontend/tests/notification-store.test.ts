import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getUnreadNotificationCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notifications';
import { useNotificationStore } from '@/stores/useNotificationStore';
import type { NotificationRead } from '@/types/notifications';

vi.mock('@/api/notifications', () => ({
  getUnreadNotificationCount: vi.fn(),
  listNotifications: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
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
