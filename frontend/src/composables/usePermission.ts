import type { RouteMeta } from 'vue-router';

import { useAuthStore, type UserRole } from '@/stores/useAuthStore';

export const PERMISSION_CODES = [
  'user.manage',
  'system.config',
  'audit_log.read',
  'database.export',
  'role_permission.manage',
  'main_project.create',
  'main_project.edit',
  'main_project.review',
  'main_project.close',
  'project.import',
  'sub_project.create',
  'sub_project.review',
  'sub_project.terminate',
  'phase.promote',
  'acceptance_step.create',
  'acceptance_step.complete',
  'payment.create',
  'payment.reverse',
  'document.upload',
  'document.download',
  'task.assign',
  'task.complete',
  'revoke_request.submit',
  'revoke_request.review',
  'report.generate',
  'project.view_all',
  'project.view_own',
] as const;

export type PermissionCode = (typeof PERMISSION_CODES)[number];

export const ROLE_PERMISSIONS: Record<UserRole, readonly PermissionCode[]> = {
  admin: [
    'user.manage',
    'system.config',
    'audit_log.read',
    'database.export',
    'role_permission.manage',
    'main_project.create',
    'main_project.edit',
    'main_project.review',
    'main_project.close',
    'project.import',
    'sub_project.create',
    'sub_project.review',
    'sub_project.terminate',
    'phase.promote',
    'acceptance_step.create',
    'acceptance_step.complete',
    'document.upload',
    'document.download',
    'task.assign',
    'task.complete',
    'revoke_request.review',
    'report.generate',
    'project.view_all',
  ],
  dept_manager: [
    'main_project.create',
    'main_project.edit',
    'main_project.review',
    'main_project.close',
    'sub_project.review',
    'sub_project.terminate',
    'acceptance_step.complete',
    'document.upload',
    'document.download',
    'task.complete',
    'revoke_request.review',
    'report.generate',
    'project.view_all',
  ],
  finance_manager: [
    'payment.create',
    'payment.reverse',
    'acceptance_step.complete',
    'document.upload',
    'document.download',
    'task.complete',
    'report.generate',
    'project.view_all',
  ],
  proj_leader: [
    'sub_project.create',
    'phase.promote',
    'acceptance_step.create',
    'acceptance_step.complete',
    'document.upload',
    'document.download',
    'task.assign',
    'task.complete',
    'revoke_request.submit',
    'project.view_own',
  ],
  proj_member: [
    'phase.promote',
    'acceptance_step.complete',
    'document.upload',
    'document.download',
    'task.complete',
    'project.view_own',
  ],
};

interface PermissionOptions {
  ownedResourceIds?: readonly string[];
  resourceId?: string;
}

const resourceScopedPermissions = new Set<PermissionCode>(['project.view_own']);

export function usePermission() {
  const authStore = useAuthStore();

  function roleHasPermission(role: UserRole, permission: PermissionCode): boolean {
    return (
      authStore.user?.permissions?.includes(permission) ??
      ROLE_PERMISSIONS[role].includes(permission)
    );
  }

  function hasRole(roles?: readonly UserRole[]): boolean {
    if (!roles?.length) {
      return true;
    }

    return Boolean(authStore.user?.role && roles.includes(authStore.user.role));
  }

  function can(permission: PermissionCode, options: PermissionOptions = {}): boolean {
    const role = authStore.user?.role;
    if (!role || !roleHasPermission(role, permission)) {
      return false;
    }

    if (!resourceScopedPermissions.has(permission) || !options.resourceId) {
      return true;
    }

    return Boolean(options.ownedResourceIds?.includes(options.resourceId));
  }

  function canAccessRoute(meta: RouteMeta): boolean {
    if (meta.public === true) {
      return true;
    }

    if (!authStore.isAuthenticated) {
      return false;
    }

    if (!hasRole(meta.requireRole)) {
      return false;
    }

    if (meta.permission && !can(meta.permission)) {
      return false;
    }

    return true;
  }

  return { can, canAccessRoute, hasRole };
}
