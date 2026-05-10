import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import router from '../src/router';
import { useAuthStore } from '../src/stores/useAuthStore';

describe('router', () => {
  beforeEach(async () => {
    setActivePinia(createPinia());
    await router.replace('/login');
  });

  it('registers the workspace home route', () => {
    const homeRoute = router.getRoutes().find((route) => route.name === 'home');
    const componentDemoRoute = router.getRoutes().find((route) => route.name === 'component-demo');
    const userManagementRoute = router.getRoutes().find((route) => route.name === 'admin-users');
    const loginRoute = router.getRoutes().find((route) => route.name === 'login');

    expect(homeRoute?.path).toBe('/');
    expect(componentDemoRoute?.path).toBe('/component-demo');
    expect(userManagementRoute?.path).toBe('/admin/users');
    expect(loginRoute?.path).toBe('/login');
  });

  it('redirects unauthenticated users to login and keeps their target path', async () => {
    await router.push('/component-demo');

    expect(router.currentRoute.value.name).toBe('login');
    expect(router.currentRoute.value.query.redirect).toBe('/component-demo');
  });

  it('redirects authenticated users away from login', async () => {
    const authStore = useAuthStore();
    authStore.setAccessToken('token-value');

    await router.push('/');
    await router.push('/login');

    expect(router.currentRoute.value.name).toBe('home');
  });

  it('redirects authenticated users away from routes outside their role', async () => {
    const authStore = useAuthStore();
    authStore.setAccessToken('member-token');
    authStore.setUser({
      id: 'member-1',
      username: 'member',
      role: 'proj_member',
      deptId: null,
    });

    await router.push('/admin/users');

    expect(router.currentRoute.value.name).toBe('home');
  });
});
