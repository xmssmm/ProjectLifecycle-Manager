export type UserRole = 'admin' | 'dept_manager' | 'finance_manager' | 'proj_leader' | 'proj_member';

export type UserStatus = 'active' | 'disabled' | 'password_reset_required';

export interface UserRead {
  created_at: string;
  dept_id: string | null;
  email: string | null;
  id: string;
  last_login_at: string | null;
  password_changed_at: string | null;
  role: UserRole;
  sso_required: boolean;
  status: UserStatus;
  updated_at: string;
  username: string;
}

export interface UserListRead {
  items: UserRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface UserListQuery {
  page: number;
  pageSize: number;
  role?: UserRole;
}

export interface UserCreatePayload {
  dept_id: string | null;
  email: string | null;
  password: string;
  role: UserRole;
  sso_required?: boolean;
  username: string;
}

export interface UserUpdatePayload {
  dept_id?: string | null;
  email?: string | null;
  role?: UserRole;
  sso_required?: boolean;
  username?: string;
}

export interface PasswordResetPayload {
  new_password: string;
}

export interface PasswordChangePayload {
  new_password: string;
  old_password: string;
}

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: '管理员',
  dept_manager: '综合部负责人',
  finance_manager: '财务负责人',
  proj_leader: '项目负责人',
  proj_member: '项目成员',
};

export const STATUS_LABELS: Record<UserStatus, string> = {
  active: '启用',
  disabled: '停用',
  password_reset_required: '需改密',
};

export const STATUS_TAG_MAP: Record<UserStatus, string> = {
  active: 'approved',
  disabled: 'archived',
  password_reset_required: 'pending_review',
};
