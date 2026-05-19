import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listRolePermissions, updateRolePermissions } from '@/api/rolePermissions';
import RolePermissionManagement from '@/views/admin/RolePermissionManagement.vue';

vi.mock('@/api/rolePermissions', () => ({
  listRolePermissions: vi.fn(),
  updateRolePermissions: vi.fn(),
}));

describe('RolePermissionManagement', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(listRolePermissions).mockResolvedValue({
      items: [
        {
          permission_codes: ['project.view_own', 'document.upload'],
          role: 'proj_member',
        },
      ],
      permissions: [
        { code: 'project.view_own', label: '查看本人项目' },
        { code: 'document.upload', label: '上传文件' },
      ],
    });
    vi.mocked(updateRolePermissions).mockResolvedValue({
      permission_codes: ['project.view_own'],
      role: 'proj_member',
    });
  });

  it('lets admins adjust role permissions from the frontend', async () => {
    const wrapper = mount(RolePermissionManagement, { global: { stubs } });
    await flushPromises();

    expect(wrapper.text()).toContain('角色权限');
    expect(wrapper.text()).toContain('上传文件');

    await wrapper.find('[data-test="permission-document.upload"]').setValue(false);
    await wrapper.find('[data-test="save-role-proj_member"]').trigger('click');
    await flushPromises();

    expect(updateRolePermissions).toHaveBeenCalledWith('proj_member', {
      permission_codes: ['project.view_own'],
    });
  });
});

const stubs = {
  ElButton: {
    props: ['loading', 'type'],
    template:
      '<button type="button" :disabled="loading" @click="$emit(\'click\')"><slot /></button>',
  },
  ElCheckbox: {
    props: ['label', 'modelValue'],
    template:
      '<label><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />{{ label }}<slot /></label>',
  },
  ElSkeleton: { template: '<section />' },
  ElTag: { template: '<span><slot /></span>' },
};
