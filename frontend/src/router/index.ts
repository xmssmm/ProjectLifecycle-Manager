import { createRouter, createWebHistory } from 'vue-router';

import { usePermission } from '@/composables/usePermission';
import { useAuthStore } from '@/stores/useAuthStore';
import ComponentDemoView from '@/views/admin/ComponentDemoView.vue';
import LoginView from '@/views/auth/LoginView.vue';
import HomeView from '@/views/HomeView.vue';

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

  if (!isPublic && !canAccessRoute(to.meta)) {
    return { name: 'home' };
  }

  return true;
});

export default router;
