import { describe, expect, it } from 'vitest';

import router from '../src/router';

describe('router', () => {
  it('registers the workspace home route', () => {
    const homeRoute = router.getRoutes().find((route) => route.name === 'home');
    const componentDemoRoute = router.getRoutes().find((route) => route.name === 'component-demo');

    expect(homeRoute?.path).toBe('/');
    expect(componentDemoRoute?.path).toBe('/component-demo');
  });
});
