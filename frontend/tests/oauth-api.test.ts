import type { AxiosAdapter, AxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';

import { createApiClient } from '../src/api/client';
import {
  bindOAuthProvider,
  completeOAuthCallback,
  listOAuthBindings,
  listOAuthProviders,
  startOAuthLogin,
  unbindOAuthProvider,
} from '../src/api/oauth';

describe('oauth api', () => {
  it('calls OAuth provider, callback, and binding endpoints', async () => {
    const calls: AxiosRequestConfig[] = [];
    const client = createApiClient('http://api.local');
    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: [{ label: '企业账号', provider: 'generic_oidc' }],
    });

    const providers = await listOAuthProviders(client);
    expect(providers[0].provider).toBe('generic_oidc');

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: { authorization_url: 'https://sso.example.local/authorize', state: 'state-1' },
    });
    await startOAuthLogin('generic_oidc', client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: { access_token: 'access', refresh_token: 'refresh', token_type: 'bearer' },
    });
    await completeOAuthCallback(
      { code: 'code-1', provider: 'generic_oidc', state: 'state-1' },
      client,
    );

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: [sampleBinding],
    });
    await listOAuthBindings(client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: sampleBinding,
    });
    await bindOAuthProvider('generic_oidc', { code: 'bind-code', state: 'bind-state' }, client);

    client.defaults.adapter = recordingAdapter(calls, {
      code: 0,
      message: 'success',
      data: { unbound: true },
    });
    await unbindOAuthProvider('generic_oidc', client);

    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      'get /oauth/providers',
      'get /oauth/generic_oidc/login',
      'get /oauth/generic_oidc/callback',
      'get /oauth/bindings',
      'post /oauth/generic_oidc/bind',
      'delete /oauth/generic_oidc/bind',
    ]);
    expect(calls[2].params).toEqual({ code: 'code-1', state: 'state-1' });
    expect(calls[4].data).toBe(JSON.stringify({ code: 'bind-code', state: 'bind-state' }));
  });
});

const sampleBinding = {
  created_at: '2026-05-10T00:00:00Z',
  email: 'admin@example.local',
  expires_at: null,
  external_id: 'external-user-1',
  id: 'binding-1',
  provider: 'generic_oidc',
  updated_at: '2026-05-10T00:00:00Z',
  user_id: 'user-1',
};

function recordingAdapter(calls: AxiosRequestConfig[], data: unknown): AxiosAdapter {
  return async (config) => {
    calls.push(config);
    return {
      config,
      data,
      headers: {},
      status: 200,
      statusText: 'OK',
    };
  };
}
