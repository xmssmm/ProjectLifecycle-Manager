import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  getUnreadNotificationCount,
  listNotifications,
  listNotificationPreferences,
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreferences,
} from '../src/api/notifications';

describe('notifications api', () => {
  it('supports list, unread count, single read, and read-all endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { items: [sampleNotification], page: 2, page_size: 10, total: 12 },
      message: 'success',
    });

    await listNotifications({ page: 2, pageSize: 10, unread: true }, client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { count: 3 },
      message: 'success',
    });
    await getUnreadNotificationCount(client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { ...sampleNotification, read_at: '2026-05-10T01:00:00Z' },
      message: 'success',
    });
    await markNotificationRead('notif-1', client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { read_count: 3 },
      message: 'success',
    });
    await markAllNotificationsRead(client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { items: [samplePreference] },
      message: 'success',
    });
    await listNotificationPreferences(client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      data: { items: [{ ...samplePreference, enabled: false }] },
      message: 'success',
    });
    await updateNotificationPreferences(
      {
        preferences: [
          {
            channels: { dingtalk: false, email: true, in_app: false, wework: false },
            scenario: 'task_assigned',
            enabled: false,
            delivery_mode: 'daily_digest',
          },
        ],
      },
      client,
    );

    expect(calls[0]).toMatchObject({
      method: 'get',
      params: { page: 2, page_size: 10, unread: true },
      url: '/notifications',
    });
    expect(calls[1]).toMatchObject({
      method: 'get',
      url: '/notifications/unread-count',
    });
    expect(calls[2]).toMatchObject({
      method: 'post',
      url: '/notifications/notif-1/read',
    });
    expect(calls[3]).toMatchObject({
      method: 'post',
      url: '/notifications/read-all',
    });
    expect(calls[4]).toMatchObject({
      method: 'get',
      url: '/notifications/preferences',
    });
    expect(calls[5]).toMatchObject({
      data: JSON.stringify({
        preferences: [
          {
            channels: { dingtalk: false, email: true, in_app: false, wework: false },
            scenario: 'task_assigned',
            enabled: false,
            delivery_mode: 'daily_digest',
          },
        ],
      }),
      method: 'put',
      url: '/notifications/preferences',
    });
  });
});

const sampleNotification = {
  created_at: '2026-05-10T00:00:00Z',
  dedup_key: 'task_assigned:user-1:task-1:20260510',
  delivery_mode: 'real_time',
  digest_sent_at: null,
  id: 'notif-1',
  payload: { task_id: 'task-1', task_no: 'Z-001-T-001' },
  read_at: null,
  receiver_id: 'user-1',
  scenario: 'task_assigned',
  source_id: 'task-1',
  updated_at: '2026-05-10T00:00:00Z',
};

const samplePreference = {
  channels: { dingtalk: false, email: false, in_app: true, wework: false },
  description: '任务执行人收到任务分配提醒',
  direct_related: true,
  delivery_mode: 'real_time',
  enabled: true,
  label: '任务分配',
  scenario: 'task_assigned',
};

function recordingAdapter(calls: AxiosRequestConfig[], data: unknown): AxiosAdapter {
  return async (config) => {
    calls.push(config);
    return {
      config,
      data,
      headers: {},
      status: 200,
      statusText: 'OK',
    };
  };
}
