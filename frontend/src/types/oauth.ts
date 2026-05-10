export interface OAuthProviderRead {
  label: string;
  provider: string;
}

export interface OAuthAuthorizationStartRead {
  authorization_url: string;
  state: string;
}

export interface OAuthBindingRead {
  created_at: string;
  email: string | null;
  expires_at: string | null;
  external_id: string;
  id: string;
  provider: string;
  updated_at: string;
  user_id: string;
}

export interface OAuthCallbackPayload {
  code: string;
  provider: string;
  state: string;
}

export interface OAuthBindPayload {
  code: string;
  state: string;
}

export interface OAuthUnbindResult {
  unbound: boolean;
}
