import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { describe, expect, it, vi } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';

import App from '../src/App.vue';
import HomeView from '../src/views/HomeView.vue';

vi.mock('@/api/tasks', () => ({
  completeTask: vi.fn(),
  createTask: vi.fn(),
  getTask: vi.fn(),
  listTasks: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  updateTask: vi.fn(),
}));

describe('App', () => {
  it('renders the workspace shell and placeholder route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: HomeView },
        { path: '/profile', component: { template: '<div />' } },
        { path: '/tasks', name: 'tasks', component: { template: '<div />' } },
      ],
    });

    router.push('/');
    await router.isReady();

    const wrapper = mount(App, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          ElAside: { template: '<aside><slot /></aside>' },
          ElButton: { template: '<button><slot /></button>' },
          ElContainer: { template: '<section><slot /></section>' },
          ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
          ElHeader: { template: '<header><slot /></header>' },
          ElIcon: { template: '<i><slot /></i>' },
          ElMain: { template: '<main><slot /></main>' },
          ElMenu: { template: '<nav><slot /></nav>' },
          ElMenuItem: { template: '<a><slot /></a>' },
          ElSegmented: {
            props: ['modelValue', 'options'],
            template:
              '<div><button v-for="option in options" :key="option.value">{{ option.label }}</button></div>',
          },
          ElTooltip: { template: '<span><slot /></span>' },
          NotificationCenter: { template: '<button>通知</button>' },
        },
      },
    });

    expect(wrapper.text()).toContain('企业项目过程管理与资料归档系统');
    expect(wrapper.text()).toContain('工作台');
  });
});
