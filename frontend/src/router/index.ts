import { createRouter, createWebHistory } from 'vue-router';

import ComponentDemoView from '@/views/admin/ComponentDemoView.vue';
import HomeView from '@/views/HomeView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/component-demo',
      name: 'component-demo',
      component: ComponentDemoView,
    },
  ],
});

export default router;
