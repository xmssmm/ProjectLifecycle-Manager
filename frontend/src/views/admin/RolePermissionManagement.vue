<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';

import { listRolePermissions, updateRolePermissions } from '@/api/rolePermissions';
import type {
  RolePermissionMatrixRead,
  RolePermissionOptionRead,
  RolePermissionRead,
} from '@/types/rolePermissions';
import type { UserRole } from '@/types/users';

const roleLabels: Record<UserRole, string> = {
  admin: '系统管理员',
  dept_manager: '部门负责人',
  finance_manager: '财务负责人',
  proj_leader: '项目负责人',
  proj_member: '项目成员',
};

const loading = ref(false);
const savingRole = ref<UserRole | null>(null);
const permissions = ref<RolePermissionOptionRead[]>([]);
const roles = ref<RolePermissionRead[]>([]);
const selectedByRole = reactive<Partial<Record<UserRole, string[]>>>({});

onMounted(loadMatrix);

async function loadMatrix(): Promise<void> {
  loading.value = true;
  try {
    applyMatrix(await listRolePermissions());
  } finally {
    loading.value = false;
  }
}

function applyMatrix(matrix: RolePermissionMatrixRead): void {
  permissions.value = matrix.permissions;
  roles.value = matrix.items;
  for (const item of matrix.items) {
    selectedByRole[item.role] = [...item.permission_codes];
  }
}

function hasPermission(role: UserRole, code: string): boolean {
  return selectedByRole[role]?.includes(code) ?? false;
}

function setPermission(role: UserRole, code: string, enabled: boolean): void {
  const current = selectedByRole[role] ?? [];
  selectedByRole[role] = enabled
    ? [...new Set([...current, code])]
    : current.filter((permission) => permission !== code);
}

function handlePermissionChange(role: UserRole, code: string, event: Event): void {
  setPermission(role, code, (event.target as HTMLInputElement).checked);
}

async function saveRole(role: UserRole): Promise<void> {
  savingRole.value = role;
  try {
    const updated = await updateRolePermissions(role, {
      permission_codes: selectedByRole[role] ?? [],
    });
    selectedByRole[role] = [...updated.permission_codes];
  } finally {
    savingRole.value = null;
  }
}
</script>

<template>
  <section class="admin-page role-permissions">
    <div class="admin-page__header">
      <div>
        <h2>角色权限</h2>
        <p>按角色控制页面入口和关键操作权限。</p>
      </div>
    </div>

    <el-skeleton v-if="loading && roles.length === 0" animated />

    <div v-else class="role-permissions__grid">
      <section v-for="role in roles" :key="role.role" class="role-permissions__role">
        <header>
          <h3>{{ roleLabels[role.role] }}</h3>
          <el-tag>{{ role.role }}</el-tag>
        </header>

        <div class="role-permissions__items">
          <label
            v-for="permission in permissions"
            :key="`${role.role}-${permission.code}`"
            class="role-permissions__item"
          >
            <!-- prettier-ignore -->
            <input
              type="checkbox"
              :checked="hasPermission(role.role, permission.code)"
              :data-test="`permission-${permission.code}`"
              @change="handlePermissionChange(role.role, permission.code, $event)"
            >
            {{ permission.label }}
          </label>
        </div>

        <el-button
          :data-test="`save-role-${role.role}`"
          :loading="savingRole === role.role"
          type="primary"
          @click="saveRole(role.role)"
        >
          保存
        </el-button>
      </section>
    </div>
  </section>
</template>

<style scoped>
.role-permissions {
  display: grid;
  gap: 18px;
}

.role-permissions__grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.role-permissions__role {
  display: grid;
  gap: 14px;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  padding: 16px;
}

.role-permissions__role header {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.role-permissions__role h3 {
  margin: 0;
}

.role-permissions__items {
  display: grid;
  gap: 8px;
}

.role-permissions__item {
  align-items: center;
  display: inline-flex;
  gap: 8px;
}
</style>
