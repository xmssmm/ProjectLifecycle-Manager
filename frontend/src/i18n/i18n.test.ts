import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createMemoryHistory, createRouter } from 'vue-router';

import StatusTag from '@/components/common/StatusTag.vue';
import AppLayout from '@/components/layout/AppLayout.vue';
import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  getCurrentLocale,
  getStatusMeta,
  setLocale,
  t,
} from '@/i18n';
import { useAuthStore } from '@/stores/useAuthStore';

vi.mock('@/components/notification/NotificationCenter.vue', () => ({
  default: {
    name: 'NotificationCenter',
    template: '<button>通知</button>',
  },
}));

describe('i18n', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    setLocale(DEFAULT_LOCALE);
  });

  it('uses Chinese as the default locale', () => {
    expect(getCurrentLocale()).toBe('zh-CN');
    expect(t('app.brand')).toBe('项目归档');
    expect(t('nav.projects')).toBe('项目');
  });

  it('switches to English and persists the selected locale', () => {
    setLocale('en-US');

    expect(getCurrentLocale()).toBe('en-US');
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('en-US');
    expect(t('app.brand')).toBe('Project Archive');
    expect(t('nav.projects')).toBe('Projects');
  });

  it('keeps status enum labels and tag types mapped across locales', () => {
    expect(getStatusMeta('in_progress')).toEqual({ label: '进行中', type: 'primary' });

    setLocale('en-US');

    expect(getStatusMeta('in_progress')).toEqual({ label: 'In progress', type: 'primary' });
    expect(getStatusMeta('unknown')).toEqual({ label: 'unknown', type: 'info' });
  });

  it('renders core layout copy in the active locale', () => {
    const authStore = useAuthStore();
    authStore.setAccessToken('admin-token');
    authStore.setUser({
      deptId: null,
      email: null,
      id: 'admin-id',
      role: 'admin',
      status: 'active',
      timezone: 'Asia/Shanghai',
      username: 'admin',
    });
    setLocale('en-US');

    const wrapper = mount(AppLayout, {
      global: {
        components: layoutComponents,
        plugins: [createLayoutRouter()],
        stubs: routerStubs,
      },
    });

    expect(wrapper.text()).toContain('Project Archive');
    expect(wrapper.text()).toContain('Projects');
    expect(wrapper.text()).toContain('Administration');
  });

  it('renders status tags in the active locale', () => {
    setLocale('en-US');

    const wrapper = mount(StatusTag, {
      props: { status: 'approved' },
    });

    expect(wrapper.text()).toBe('Approved');
    expect(wrapper.attributes('data-type')).toBe('success');
  });
});

function createLayoutRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/profile', component: { template: '<div />' } },
    ],
  });
}

const layoutComponents = {
  ElAside: { name: 'ElAside', template: '<aside><slot /></aside>' },
  ElButton: { name: 'ElButton', template: '<button><slot /></button>' },
  ElContainer: { name: 'ElContainer', template: '<section><slot /></section>' },
  ElHeader: { name: 'ElHeader', template: '<header><slot /></header>' },
  ElIcon: { name: 'ElIcon', template: '<i><slot /></i>' },
  ElMain: { name: 'ElMain', template: '<main><slot /></main>' },
  ElMenu: { name: 'ElMenu', template: '<nav><slot /></nav>' },
  ElMenuItem: {
    name: 'ElMenuItem',
    props: ['disabled', 'index'],
    template: '<a :href="index" :aria-disabled="disabled"><slot /></a>',
  },
  ElSegmented: {
    name: 'ElSegmented',
    props: ['modelValue', 'options'],
    template: '<div><button v-for="option in options" :key="option.value">{{ option.label }}</button></div>',
  },
  ElTooltip: { name: 'ElTooltip', template: '<span><slot /></span>' },
};

const routerStubs = {
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
  RouterView: { template: '<div />' },
};
