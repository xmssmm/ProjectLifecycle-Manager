import type { UserRole } from '@/types/users';

export interface RolePermissionOptionRead {
  code: string;
  label: string;
}

export interface RolePermissionRead {
  permission_codes: string[];
  role: UserRole;
}

export interface RolePermissionMatrixRead {
  items: RolePermissionRead[];
  permissions: RolePermissionOptionRead[];
}

export interface RolePermissionUpdate {
  permission_codes: string[];
}
