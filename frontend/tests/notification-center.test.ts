import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getUnreadNotificationCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notifications';
import NotificationCenter from '@/components/notification/NotificationCenter.vue';
import type { NotificationRead } from '@/types/notifications';

vi.mock('@/api/notifications', () => ({
  getUnreadNotificationCount: vi.fn(),
  listNotifications: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
}));

describe('NotificationCenter', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(getUnreadNotificationCount).mockResolvedValue({ count: 2 });
    vi.mocked(listNotifications).mockResolvedValue({
      items: [taskNotification, paymentNotification],
      page: 1,
      page_size: 10,
      total: 2,
    });
    vi.mocked(markNotificationRead).mockResolvedValue({
      ...taskNotification,
      read_at: '2026-05-10T01:00:00Z',
    });
    vi.mocked(markAllNotificationsRead).mockResolvedValue({ read_count: 1 });
  });

  it('shows unread count, opens the panel, links to business pages, and marks read', async () => {
    const wrapper = mount(NotificationCenter, { global: { stubs } });
    await flushPromises();

    expect(getUnreadNotificationCount).toHaveBeenCalled();
    expect(wrapper.find('[data-test="notification-unread-count"]').text()).toBe('2');

    await wrapper.find('[data-test="notification-trigger"]').trigger('click');
    await flushPromises();

    expect(listNotifications).toHaveBeenCalledWith({ page: 1, pageSize: 10 });
    expect(wrapper.find('[data-test="notification-panel"]').classes()).toContain(
      'notification-center__panel--touch',
    );
    expect(wrapper.text()).toContain('任务指派');
    expect(wrapper.text()).toContain('Z-001-T-001');
    expect(wrapper.find('[data-test="notification-link-notif-1"]').attributes('to')).toBe(
      '/tasks/task-1',
    );
    expect(wrapper.find('[data-test="notification-link-notif-2"]').attributes('to')).toBe(
      '/sub-projects/sub-1/payments',
    );

    await wrapper.find('[data-test="mark-notification-read-notif-1"]').trigger('click');
    await flushPromises();

    expect(markNotificationRead).toHaveBeenCalledWith('notif-1');

    await wrapper.find('[data-test="mark-all-notifications-read"]').trigger('click');
    await flushPromises();

    expect(markAllNotificationsRead).toHaveBeenCalled();
  });
});

const taskNotification: NotificationRead = {
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

const paymentNotification: NotificationRead = {
  ...taskNotification,
  id: 'notif-2',
  payload: { amount: '100.00', payment_id: 'payment-1', sub_project_id: 'sub-1' },
  scenario: 'payment_created',
  source_id: 'payment-1',
};

const stubs = {
  ElBadge: {
    props: ['hidden', 'value'],
    template:
      '<span><slot /><span v-if="!hidden" data-test="notification-unread-count">{{ value }}</span></span>',
  },
  ElButton: {
    emits: ['click'],
    props: ['circle', 'disabled', 'icon', 'loading', 'text', 'type'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElIcon: { template: '<i><slot /></i>' },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
  RouterLink: { props: ['to'], template: '<a :to="to"><slot /></a>' },
};
