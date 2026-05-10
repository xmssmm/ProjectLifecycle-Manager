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
    const dashboardRoute = router.getRoutes().find((route) => route.name === 'dashboard');
    const componentDemoRoute = router.getRoutes().find((route) => route.name === 'component-demo');
    const userManagementRoute = router.getRoutes().find((route) => route.name === 'admin-users');
    const departmentRoute = router.getRoutes().find((route) => route.name === 'admin-departments');
    const auditLogRoute = router.getRoutes().find((route) => route.name === 'admin-audit-logs');
    const handoverRoute = router.getRoutes().find((route) => route.name === 'admin-handover');
    const handoverHistoryRoute = router
      .getRoutes()
      .find((route) => route.name === 'admin-handover-history');
    const mainProjectRoute = router.getRoutes().find((route) => route.name === 'main-projects');
    const mainProjectDetailRoute = router
      .getRoutes()
      .find((route) => route.name === 'main-project-detail');
    const mainProjectCreateRoute = router
      .getRoutes()
      .find((route) => route.name === 'main-project-create');
    const mainProjectEditRoute = router
      .getRoutes()
      .find((route) => route.name === 'main-project-edit');
    const mainProjectReviewRoute = router
      .getRoutes()
      .find((route) => route.name === 'main-project-review');
    const subProjectRoute = router.getRoutes().find((route) => route.name === 'sub-projects');
    const subProjectDetailRoute = router
      .getRoutes()
      .find((route) => route.name === 'sub-project-detail');
    const subProjectCreateRoute = router
      .getRoutes()
      .find((route) => route.name === 'sub-project-create');
    const subProjectEditRoute = router
      .getRoutes()
      .find((route) => route.name === 'sub-project-edit');
    const subProjectReviewRoute = router
      .getRoutes()
      .find((route) => route.name === 'sub-project-review');
    const subProjectPaymentsRoute = router
      .getRoutes()
      .find((route) => route.name === 'sub-project-payments');
    const revokeRequestsRoute = router
      .getRoutes()
      .find((route) => route.name === 'revoke-requests');
    const revokeApplyRoute = router.getRoutes().find((route) => route.name === 'revoke-apply');
    const revokeReviewRoute = router.getRoutes().find((route) => route.name === 'revoke-review');
    const profileRoute = router.getRoutes().find((route) => route.name === 'profile');
    const passwordRoute = router.getRoutes().find((route) => route.name === 'change-password');
    const loginRoute = router.getRoutes().find((route) => route.name === 'login');

    expect(homeRoute?.path).toBe('/');
    expect(dashboardRoute?.path).toBe('/dashboard');
    expect(componentDemoRoute?.path).toBe('/component-demo');
    expect(userManagementRoute?.path).toBe('/admin/users');
    expect(departmentRoute?.path).toBe('/admin/departments');
    expect(auditLogRoute?.path).toBe('/admin/audit-logs');
    expect(handoverRoute?.path).toBe('/admin/handover');
    expect(handoverHistoryRoute?.path).toBe('/admin/handover/history');
    expect(mainProjectRoute?.path).toBe('/main-projects');
    expect(mainProjectDetailRoute?.path).toBe('/main-projects/:id');
    expect(mainProjectCreateRoute?.path).toBe('/main-projects/new');
    expect(mainProjectEditRoute?.path).toBe('/main-projects/:id/edit');
    expect(mainProjectReviewRoute?.path).toBe('/main-projects/:id/review');
    expect(subProjectRoute?.path).toBe('/sub-projects');
    expect(subProjectDetailRoute?.path).toBe('/sub-projects/:id');
    expect(subProjectCreateRoute?.path).toBe('/sub-projects/new');
    expect(subProjectEditRoute?.path).toBe('/sub-projects/:id/edit');
    expect(subProjectReviewRoute?.path).toBe('/sub-projects/:id/review');
    expect(subProjectPaymentsRoute?.path).toBe('/sub-projects/:id/payments');
    expect(revokeRequestsRoute?.path).toBe('/revoke-requests');
    expect(revokeApplyRoute?.path).toBe('/sub-projects/:id/revoke');
    expect(revokeReviewRoute?.path).toBe('/revoke-requests/review');
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
