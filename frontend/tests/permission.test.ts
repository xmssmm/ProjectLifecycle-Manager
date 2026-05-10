import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';

import AppLayout from '../src/components/layout/AppLayout.vue';
import PermissionGate from '../src/components/permission/PermissionGate.vue';
import { useAuthStore } from '../src/stores/useAuthStore';

const layoutStubs = {
  ElAside: { template: '<aside><slot /></aside>' },
  ElButton: { template: '<button><slot /></button>' },
  ElContainer: { template: '<section><slot /></section>' },
  ElHeader: { template: '<header><slot /></header>' },
  ElIcon: { template: '<i><slot /></i>' },
  ElMain: { template: '<main><slot /></main>' },
  ElMenu: { template: '<nav><slot /></nav>' },
  ElMenuItem: {
    props: ['index'],
    template: '<a :href="index"><slot /></a>',
  },
  ElTooltip: { template: '<span><slot /></span>' },
  RouterView: { template: '<div />' },
};

function setUser(role: 'admin' | 'dept_manager' | 'finance_manager' | 'proj_leader' | 'proj_member') {
  const authStore = useAuthStore();
  authStore.setAccessToken(`${role}-token`);
  authStore.setUser({
    id: `${role}-id`,
    username: role,
    role,
    deptId: null,
  });
}

describe('frontend permissions', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('PermissionGate renders by current user permission and supports fallback', () => {
    setUser('finance_manager');

    const allowed = mount(PermissionGate, {
      props: { permission: 'payment.create' },
      slots: { default: 'allowed', fallback: 'fallback' },
    });
    const denied = mount(PermissionGate, {
      props: { permission: 'user.manage' },
      slots: { default: 'allowed', fallback: 'fallback' },
    });

    expect(allowed.text()).toBe('allowed');
    expect(denied.text()).toBe('fallback');
  });

  it('sidebar hides admin-only entries for project members', () => {
    setUser('proj_member');

    const wrapper = mount(AppLayout, {
      global: {
        plugins: [
          createRouter({
            history: createMemoryHistory(),
            routes: [{ path: '/', component: { template: '<div />' } }],
          }),
        ],
        stubs: layoutStubs,
      },
    });

    const menuLabels = wrapper.findAll('a').map((item) => item.text());

    expect(menuLabels).toContain('工作台');
    expect(menuLabels).toContain('项目');
    expect(menuLabels).not.toContain('组件');
    expect(menuLabels).not.toContain('管理');
  });

  it('sidebar shows admin-only entries for admins', () => {
    setUser('admin');

    const wrapper = mount(AppLayout, {
      global: {
        plugins: [
          createRouter({
            history: createMemoryHistory(),
            routes: [{ path: '/', component: { template: '<div />' } }],
          }),
        ],
        stubs: layoutStubs,
      },
    });

    const menuLabels = wrapper.findAll('a').map((item) => item.text());

    expect(menuLabels).toContain('组件');
    expect(menuLabels).toContain('管理');
  });
});
