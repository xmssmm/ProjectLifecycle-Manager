import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  getUnreadNotificationCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
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
  });
});

const sampleNotification = {
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
