import { createRouter, createWebHistory } from 'vue-router';

import { usePermission } from '@/composables/usePermission';
import { useAuthStore } from '@/stores/useAuthStore';
import ComponentDemoView from '@/views/admin/ComponentDemoView.vue';
import DepartmentListView from '@/views/admin/DepartmentList.vue';
import HandoverHistoryView from '@/views/admin/HandoverHistory.vue';
import UserHandoverView from '@/views/admin/UserHandover.vue';
import UserListView from '@/views/admin/UserList.vue';
import LoginView from '@/views/auth/LoginView.vue';
import ChangePasswordView from '@/views/ChangePassword.vue';
import HomeView from '@/views/HomeView.vue';
import MainProjectDetailView from '@/views/main-project/MainProjectDetail.vue';
import MainProjectEditView from '@/views/main-project/MainProjectEdit.vue';
import MainProjectListView from '@/views/main-project/MainProjectList.vue';
import MainProjectReviewView from '@/views/main-project/MainProjectReview.vue';
import PaymentListView from '@/views/payment/PaymentList.vue';
import ProfileView from '@/views/Profile.vue';
import SubProjectDetailView from '@/views/sub-project/SubProjectDetail.vue';
import SubProjectEditView from '@/views/sub-project/SubProjectEdit.vue';
import SubProjectListView from '@/views/sub-project/SubProjectList.vue';
import SubProjectReviewView from '@/views/sub-project/SubProjectReview.vue';
import TaskDetailView from '@/views/task/TaskDetail.vue';
import TaskListView from '@/views/task/TaskList.vue';

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
      path: '/admin/handover',
      name: 'admin-handover',
      component: UserHandoverView,
      meta: { requireRole: ['admin'], requiresAuth: true },
    },
    {
      path: '/admin/handover/history',
      name: 'admin-handover-history',
      component: HandoverHistoryView,
      meta: { requireRole: ['admin'], requiresAuth: true },
    },
    {
      path: '/main-projects',
      name: 'main-projects',
      component: MainProjectListView,
      meta: { permission: 'project.view_all', requiresAuth: true },
    },
    {
      path: '/main-projects/new',
      name: 'main-project-create',
      component: MainProjectEditView,
      meta: { permission: 'main_project.create', requiresAuth: true },
    },
    {
      path: '/main-projects/:id/edit',
      name: 'main-project-edit',
      component: MainProjectEditView,
      meta: { permission: 'main_project.edit', requiresAuth: true },
      props: (route) => ({ projectId: String(route.params.id) }),
    },
    {
      path: '/main-projects/:id/review',
      name: 'main-project-review',
      component: MainProjectReviewView,
      meta: { permission: 'main_project.review', requiresAuth: true },
      props: (route) => ({ projectId: String(route.params.id) }),
    },
    {
      path: '/main-projects/:id',
      name: 'main-project-detail',
      component: MainProjectDetailView,
      meta: { permission: 'project.view_all', requiresAuth: true },
      props: (route) => ({ projectId: String(route.params.id) }),
    },
    {
      path: '/sub-projects',
      name: 'sub-projects',
      component: SubProjectListView,
      meta: { requiresAuth: true },
    },
    {
      path: '/sub-projects/new',
      name: 'sub-project-create',
      component: SubProjectEditView,
      meta: { permission: 'sub_project.create', requiresAuth: true },
    },
    {
      path: '/sub-projects/:id/edit',
      name: 'sub-project-edit',
      component: SubProjectEditView,
      meta: { permission: 'sub_project.create', requiresAuth: true },
      props: (route) => ({ subProjectId: String(route.params.id) }),
    },
    {
      path: '/sub-projects/:id/review',
      name: 'sub-project-review',
      component: SubProjectReviewView,
      meta: { permission: 'sub_project.review', requiresAuth: true },
      props: (route) => ({ subProjectId: String(route.params.id) }),
    },
    {
      path: '/sub-projects/:id/payments',
      name: 'sub-project-payments',
      component: PaymentListView,
      meta: { requiresAuth: true },
      props: (route) => ({ subProjectId: String(route.params.id) }),
    },
    {
      path: '/sub-projects/:id',
      name: 'sub-project-detail',
      component: SubProjectDetailView,
      meta: { requiresAuth: true },
      props: (route) => ({ subProjectId: String(route.params.id) }),
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: TaskListView,
      meta: { requiresAuth: true },
    },
    {
      path: '/tasks/:id',
      name: 'task-detail',
      component: TaskDetailView,
      meta: { requiresAuth: true },
      props: (route) => ({ taskId: String(route.params.id) }),
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
