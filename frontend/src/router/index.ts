import { createRouter, createWebHistory } from 'vue-router';

import { usePermission } from '@/composables/usePermission';
import { useAuthStore } from '@/stores/useAuthStore';
import ComponentDemoView from '@/views/admin/ComponentDemoView.vue';
import DepartmentListView from '@/views/admin/DepartmentList.vue';
import UserListView from '@/views/admin/UserList.vue';
import LoginView from '@/views/auth/LoginView.vue';
import ChangePasswordView from '@/views/ChangePassword.vue';
import HomeView from '@/views/HomeView.vue';
import MainProjectDetailView from '@/views/main-project/MainProjectDetail.vue';
import MainProjectListView from '@/views/main-project/MainProjectList.vue';
import ProfileView from '@/views/Profile.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true },
    },
    {
      path: '/component-demo',
      name: 'component-demo',
      component: ComponentDemoView,
      meta: { requireRole: ['admin'], requiresAuth: true },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: UserListView,
      meta: { requireRole: ['admin'], requiresAuth: true },
    },
    {
      path: '/admin/departments',
      name: 'admin-departments',
      component: DepartmentListView,
      meta: { requireRole: ['admin'], requiresAuth: true },
    },
    {
      path: '/main-projects',
      name: 'main-projects',
      component: MainProjectListView,
      meta: { permission: 'project.view_all', requiresAuth: true },
    },
    {
      path: '/main-projects/:id',
      name: 'main-project-detail',
      component: MainProjectDetailView,
      meta: { permission: 'project.view_all', requiresAuth: true },
      props: (route) => ({ projectId: String(route.params.id) }),
    },
    {
      path: '/profile',
      name: 'profile',
      component: ProfileView,
      meta: { requiresAuth: true },
    },
    {
      path: '/change-password',
      name: 'change-password',
      component: ChangePasswordView,
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { layout: 'auth', public: true },
    },
  ],
});

router.beforeEach((to) => {
  const authStore = useAuthStore();
  const { canAccessRoute } = usePermission();
  const isPublic = to.meta.public === true;

  if (to.name === 'login' && authStore.isAuthenticated) {
    return { name: 'home' };
  }

  if (!isPublic && !authStore.isAuthenticated) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },
    };
  }

  if (
    !isPublic &&
    authStore.user?.status === 'password_reset_required' &&
    to.name !== 'change-password'
  ) {
    return { name: 'change-password' };
  }

  if (!isPublic && !canAccessRoute(to.meta)) {
    return { name: 'home' };
  }

  return true;
});

export default router;
