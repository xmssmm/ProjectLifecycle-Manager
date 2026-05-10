import { defineStore } from 'pinia';

import {
  getUnreadNotificationCount,
  listNotifications,
  listNotificationPreferences,
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreferences,
} from '@/api/notifications';
import type {
  NotificationListQuery,
  NotificationPreferenceRead,
  NotificationPreferenceUpdateItem,
  NotificationRead,
} from '@/types/notifications';

interface NotificationState {
  loading: boolean;
  notifications: NotificationRead[];
  preferences: NotificationPreferenceRead[];
  preferencesLoading: boolean;
  preferencesSaving: boolean;
  pollingTimer: number | null;
  total: number;
  unreadCount: number;
}

export const useNotificationStore = defineStore('notifications', {
  state: (): NotificationState => ({
    loading: false,
    notifications: [],
    preferences: [],
    preferencesLoading: false,
    preferencesSaving: false,
    pollingTimer: null,
    total: 0,
    unreadCount: 0,
  }),
  actions: {
    async fetchNotifications(query: NotificationListQuery = {}) {
      this.loading = true;
      try {
        const result = await listNotifications(query);
        this.notifications = result.items;
        this.total = result.total;
        return result;
      } finally {
        this.loading = false;
      }
    },
    async fetchUnreadCount() {
      const result = await getUnreadNotificationCount();
      this.unreadCount = result.count;
      return result;
    },
    async fetchPreferences() {
      this.preferencesLoading = true;
      try {
        const result = await listNotificationPreferences();
        this.preferences = result.items;
        return result;
      } finally {
        this.preferencesLoading = false;
      }
    },
    async savePreferences(preferences: NotificationPreferenceUpdateItem[]) {
      this.preferencesSaving = true;
      try {
        const result = await updateNotificationPreferences({ preferences });
        this.preferences = result.items;
        return result;
      } finally {
        this.preferencesSaving = false;
      }
    },
    async markRead(notificationId: string) {
      const existing = this.notifications.find((item) => item.id === notificationId);
      const wasUnread = existing?.read_at === null;
      const notification = await markNotificationRead(notificationId);
      this.upsertNotification(notification);
      if (wasUnread && notification.read_at !== null) {
        this.unreadCount = Math.max(0, this.unreadCount - 1);
      }
      return notification;
    },
    async markAllRead() {
      const result = await markAllNotificationsRead();
      if (result.read_count > 0) {
        const readAt = new Date().toISOString();
        this.notifications = this.notifications.map((notification) => ({
          ...notification,
          read_at: notification.read_at ?? readAt,
        }));
      }
      this.unreadCount = Math.max(0, this.unreadCount - result.read_count);
      return result;
    },
    startUnreadPolling(intervalMs = 30000) {
      this.stopUnreadPolling();
      this.pollingTimer = window.setInterval(() => {
        void this.fetchUnreadCount();
      }, intervalMs);
    },
    stopUnreadPolling() {
      if (this.pollingTimer === null) {
        return;
      }
      window.clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    },
    upsertNotification(notification: NotificationRead) {
      const existingIndex = this.notifications.findIndex((item) => item.id === notification.id);
      if (existingIndex >= 0) {
        this.notifications.splice(existingIndex, 1, notification);
        return;
      }
      this.notifications = [notification, ...this.notifications];
      this.total = Math.max(this.total, this.notifications.length);
    },
  },
});
