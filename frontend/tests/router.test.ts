import { describe, expect, it } from 'vitest';

import router from '../src/router';

describe('router', () => {
  it('registers the workspace home route', () => {
    const homeRoute = router.getRoutes().find((route) => route.name === 'home');

    expect(homeRoute?.path).toBe('/');
  });
});
