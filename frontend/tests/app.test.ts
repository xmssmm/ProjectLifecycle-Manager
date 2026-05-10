import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { describe, expect, it } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';

import App from '../src/App.vue';
import HomeView from '../src/views/HomeView.vue';

describe('App', () => {
  it('renders the workspace shell and placeholder route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: HomeView }],
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
          ElHeader: { template: '<header><slot /></header>' },
          ElIcon: { template: '<i><slot /></i>' },
          ElMain: { template: '<main><slot /></main>' },
          ElMenu: { template: '<nav><slot /></nav>' },
          ElMenuItem: { template: '<a><slot /></a>' },
          ElTooltip: { template: '<span><slot /></span>' },
        },
      },
    });

    expect(wrapper.text()).toContain('企业项目过程管理与资料归档系统');
    expect(wrapper.text()).toContain('工作台');
  });
});
