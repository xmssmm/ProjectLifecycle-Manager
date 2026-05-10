import type { PermissionCode } from '@/composables/usePermission';
import type { UserRole } from '@/stores/useAuthStore';

declare module 'vue-router' {
  interface RouteMeta {
    layout?: 'app' | 'auth';
    permission?: PermissionCode;
    public?: boolean;
    requireRole?: UserRole[];
    requiresAuth?: boolean;
  }
}
