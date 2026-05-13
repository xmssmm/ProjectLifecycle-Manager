import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listPhases, promotePhase } from '@/api/phases';
import { useAuthStore } from '@/stores/useAuthStore';
import type { PhaseRead } from '@/types/phases';
import PhaseProgress from '@/components/phase/PhaseProgress.vue';

vi.mock('@/api/phases', () => ({
  getPhase: vi.fn(),
  listPhases: vi.fn(),
  promotePhase: vi.fn(),
  updateProcurementType: vi.fn(),
}));

describe('PhaseProgress', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    const authStore = useAuthStore();
    authStore.setAccessToken('leader-token');
    authStore.setUser({
      deptId: 'dept-a',
      email: null,
      id: 'leader-1',
      role: 'proj_leader',
      status: 'active',
      username: 'leader',
    });
    vi.mocked(listPhases).mockResolvedValue({ items: [phaseOne, phaseTwo, phaseThree], total: 3 });
    vi.mocked(promotePhase).mockResolvedValue({
      activated_phase: { ...phaseThree, status: 'in_progress' },
      phase: { ...phaseTwo, status: 'completed' },
    });
  });

  it('renders ordered phases and promotes the active phase', async () => {
    const wrapper = mount(PhaseProgress, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    expect(listPhases).toHaveBeenCalledWith({ subProjectId: 'sub-1' });
    const phaseItems = wrapper.findAll('[data-test="phase-item"]');
    expect(phaseItems).toHaveLength(3);
    expect(phaseItems[1].text()).toContain('合同签订');
    expect(wrapper.find('[data-test="mobile-read-only-phase"]').text()).toContain(
      '移动端仅支持查看环节进度',
    );
    expect(wrapper.find('[data-test="promote-phase-2"]').classes()).toContain(
      'desktop-only-action',
    );

    await wrapper.find('[data-test="promote-phase-2"]').trigger('click');
    await flushPromises();

    expect(promotePhase).toHaveBeenCalledWith('phase-2');
    expect(wrapper.findAll('[data-test="phase-status-code"]')[1].text()).toBe('completed');
    expect(wrapper.findAll('[data-test="phase-status-code"]')[2].text()).toBe('in_progress');
  });
});

const phaseOne: PhaseRead = {
  code: 'init',
  created_at: '2026-05-10T00:00:00Z',
  enter_at: '2026-05-10T00:00:00Z',
  finish_at: '2026-05-11T00:00:00Z',
  id: 'phase-1',
  name: '立项',
  phase_no: 1,
  procurement_type: null,
  status: 'completed',
  sub_project_id: 'sub-1',
  updated_at: '2026-05-11T00:00:00Z',
};

const phaseTwo: PhaseRead = {
  ...phaseOne,
  code: 'contract',
  finish_at: null,
  id: 'phase-2',
  name: '合同签订',
  phase_no: 2,
  status: 'in_progress',
};

const phaseThree: PhaseRead = {
  ...phaseOne,
  code: 'deliver',
  enter_at: null,
  finish_at: null,
  id: 'phase-3',
  name: '供货验收',
  phase_no: 3,
  status: 'waiting',
};

const stubs = {
  ElButton: {
    emits: ['click'],
    props: ['disabled', 'loading', 'type'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElProgress: { props: ['percentage'], template: '<progress>{{ percentage }}</progress>' },
};
