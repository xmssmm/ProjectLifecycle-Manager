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
    const departmentRoute = router.getRoutes().find((route) => route.name === 'admin-departments');
    const mainProjectRoute = router.getRoutes().find((route) => route.name === 'main-projects');
    const mainProjectDetailRoute = router
      .getRoutes()
      .find((route) => route.name === 'main-project-detail');
    const profileRoute = router.getRoutes().find((route) => route.name === 'profile');
    const passwordRoute = router.getRoutes().find((route) => route.name === 'change-password');
    const loginRoute = router.getRoutes().find((route) => route.name === 'login');

    expect(homeRoute?.path).toBe('/');
    expect(componentDemoRoute?.path).toBe('/component-demo');
    expect(userManagementRoute?.path).toBe('/admin/users');
    expect(departmentRoute?.path).toBe('/admin/departments');
    expect(mainProjectRoute?.path).toBe('/main-projects');
    expect(mainProjectDetailRoute?.path).toBe('/main-projects/:id');
    expect(profileRoute?.path).toBe('/profile');
    expect(passwordRoute?.path).toBe('/change-password');
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
      deptId: null,
      email: null,
      id: 'member-1',
      role: 'proj_member',
      status: 'active',
      username: 'member',
    });

    await router.push('/admin/users');

    expect(router.currentRoute.value.name).toBe('home');
  });

  it('forces password-reset users to the change password page', async () => {
    const authStore = useAuthStore();
    authStore.setAccessToken('reset-token');
    authStore.setUser({
      deptId: null,
      email: null,
      id: 'reset-1',
      role: 'proj_member',
      status: 'password_reset_required',
      username: 'reset-user',
    });

    await router.push('/');

    expect(router.currentRoute.value.name).toBe('change-password');
  });
});
