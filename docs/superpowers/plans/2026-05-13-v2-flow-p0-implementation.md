# V2 Flow P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the verified V2 flow blockers that prevent users from creating projects, selecting business entities, uploading readable documents, choosing procurement type, and promoting phases from the working context.

**Architecture:** Keep existing backend services and state machine foundations. Add missing read fields, mutation endpoints, and frontend controls around the existing models instead of rebuilding payment or acceptance-step services that already passed validation. Implement P0 in vertical slices so each task has tests and can be shipped independently.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Pydantic, pytest, Vue 3, Pinia, Element Plus, Vitest, TypeScript, PowerShell on Windows.

---

## Scope

This plan implements the verified P0 items from `docs/V2_ISSUE_VALIDATION_REPORT.md`:

- Department, main-project, and sub-project ID inputs become business selectors.
- Main/sub project lists show human-readable names and key business fields.
- Sub-project creation explains the workflow and avoids raw main project / department IDs.
- Phase document context has a promote action and clear blockers.
- Procurement phase has a procurement type selection path and inquiry requires 3 supplier quotes.
- Documents have a user-facing `display_name` used in lists and previews.

This plan intentionally does not reimplement payment spent-amount recalculation, acceptance-step creation, acceptance-step document association, or base phase promotion. Those already exist and have passing targeted tests.

Deferred after this P0 plan: stepped-acceptance toggle, acceptance responsible name display, explicit "my responsible / my participating" filter, and approved-main-project modification approval.

---

## File Structure

### Backend

- Modify `backend/app/models/documents.py` to add `display_name`.
- Modify `backend/app/schemas/documents.py` to expose `display_name`.
- Modify `backend/app/api/v1/documents.py` to accept optional upload `display_name`.
- Modify `backend/app/services/documents.py` to persist cleaned `display_name`, defaulting to original file name.
- Create `backend/alembic/versions/0037_add_document_display_name.py`.
- Modify `backend/app/schemas/main_projects.py` and `backend/app/api/v1/main_projects.py` to include `dept_name`, `creator_name`, and `remaining_amount`.
- Modify `backend/app/schemas/sub_projects.py` and `backend/app/api/v1/sub_projects.py` to include `dept_name`, `main_project_name`, `manager_name`, and `remaining_amount`.
- Modify `backend/app/services/main_projects.py` and `backend/app/services/sub_projects.py` to eager-load related department/user/main-project data for list/detail reads.
- Modify `backend/app/schemas/phases.py`, `backend/app/services/phases.py`, and `backend/app/api/v1/phases.py` to support procurement type update.
- Modify `backend/app/seeds/phase_doc_templates.py` and `backend/app/seeds/workflow_templates.py` so inquiry procurement requires `supplier_quote >=3`.
- Test in `backend/tests/unit/test_main_project_management.py`, `backend/tests/unit/test_sub_project_management.py`, `backend/tests/unit/test_document_upload.py`, `backend/tests/unit/test_document_models.py`, and `backend/tests/unit/test_phase_promote.py`.

### Frontend

- Create `frontend/src/components/form/DepartmentSelect.vue`.
- Create `frontend/src/components/form/MainProjectSelect.vue`.
- Modify `frontend/src/types/departments.ts`, `frontend/src/types/projects.ts`, `frontend/src/types/documents.ts`, and `frontend/src/types/phases.ts`.
- Modify `frontend/src/api/documents.ts`, `frontend/src/api/phases.ts`, and `frontend/src/api/subProjects.ts`.
- Modify `frontend/src/views/admin/UserEdit.vue`.
- Modify `frontend/src/views/admin/DepartmentList.vue`.
- Modify `frontend/src/views/main-project/MainProjectEdit.vue`.
- Modify `frontend/src/views/main-project/MainProjectReview.vue`.
- Modify `frontend/src/views/main-project/MainProjectList.vue`.
- Modify `frontend/src/views/main-project/MainProjectDetail.vue`.
- Modify `frontend/src/views/sub-project/SubProjectEdit.vue`.
- Modify `frontend/src/views/sub-project/SubProjectList.vue`.
- Modify `frontend/src/views/sub-project/SubProjectDetail.vue`.
- Modify `frontend/src/components/document/DocumentUploader.vue`.
- Modify `frontend/src/components/document/DocumentList.vue`.
- Modify `frontend/src/components/document/PdfPreview.vue`.
- Modify `frontend/src/components/phase/PhaseDocumentPanel.vue`.
- Test with new or existing Vitest specs under `frontend/src/views/**/*.test.ts` and `frontend/src/components/**/*.test.ts`.

---

## Task 1: Backend Project Read Models Expose Business Names

**Files:**

- Modify: `backend/app/schemas/main_projects.py`
- Modify: `backend/app/schemas/sub_projects.py`
- Modify: `backend/app/api/v1/main_projects.py`
- Modify: `backend/app/api/v1/sub_projects.py`
- Modify: `backend/app/services/main_projects.py`
- Modify: `backend/app/services/sub_projects.py`
- Test: `backend/tests/unit/test_main_project_management.py`
- Test: `backend/tests/unit/test_sub_project_management.py`

- [ ] **Step 1: Add failing tests for main project list business fields**

Append this test to `backend/tests/unit/test_main_project_management.py` near the existing read/list tests:

```python
def test_main_project_read_serializes_names_and_remaining_amount() -> None:
    project = MainProjectFactory(
        total_budget=Decimal("500000.00"),
        spent_amount=Decimal("125000.00"),
    )
    project.department = DepartmentFactory(id=project.dept_id, name="行政部", code="XZ")
    project.creator = UserFactory(id=project.creator_id, username="综合部负责人")

    payload = MainProjectRead.model_validate(project).model_dump()

    assert payload["dept_name"] == "行政部"
    assert payload["creator_name"] == "综合部负责人"
    assert payload["remaining_amount"] == Decimal("375000.00")
```

- [ ] **Step 2: Add failing tests for sub project list business fields**

Append this test to `backend/tests/unit/test_sub_project_management.py`:

```python
def test_sub_project_read_serializes_names_and_remaining_amount() -> None:
    sub_project = SubProjectFactory(
        budget=Decimal("200000.00"),
        spent_amount=Decimal("54000.00"),
    )
    sub_project.department = DepartmentFactory(id=sub_project.dept_id, name="行政部", code="XZ")
    sub_project.main_project = MainProjectFactory(
        id=sub_project.main_project_id,
        name="2026办公设备升级",
    )
    sub_project.manager = UserFactory(id=sub_project.manager_id, username="张三")

    payload = SubProjectRead.model_validate(sub_project).model_dump()

    assert payload["dept_name"] == "行政部"
    assert payload["main_project_name"] == "2026办公设备升级"
    assert payload["manager_name"] == "张三"
    assert payload["remaining_amount"] == Decimal("146000.00")
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_main_project_management.py::test_main_project_read_serializes_names_and_remaining_amount tests/unit/test_sub_project_management.py::test_sub_project_read_serializes_names_and_remaining_amount
```

Expected: both tests fail because the new schema fields do not exist.

- [ ] **Step 4: Add computed fields to backend schemas**

In `backend/app/schemas/main_projects.py`, import `computed_field` from Pydantic and add these fields to `MainProjectRead`:

```python
    @computed_field
    @property
    def dept_name(self) -> str | None:
        department = getattr(self, "department", None)
        return getattr(department, "name", None)

    @computed_field
    @property
    def creator_name(self) -> str | None:
        creator = getattr(self, "creator", None)
        return getattr(creator, "username", None)

    @computed_field
    @property
    def remaining_amount(self) -> Decimal:
        return self.total_budget - self.spent_amount
```

If Pydantic computed fields cannot access SQLAlchemy relationships after validation, replace this with explicit serializer functions in `backend/app/api/v1/main_projects.py`:

```python
def serialize_main_project(project: MainProject) -> dict[str, object]:
    payload = MainProjectRead.model_validate(project).model_dump(mode="json")
    payload["dept_name"] = project.department.name if project.department else None
    payload["creator_name"] = project.creator.username if project.creator else None
    payload["remaining_amount"] = str(project.total_budget - project.spent_amount)
    return payload
```

Use the serializer approach if the test confirms computed fields are unsuitable for ORM relationship access.

- [ ] **Step 5: Add matching sub project serializer fields**

In `backend/app/api/v1/sub_projects.py`, update `serialize_sub_project`:

```python
def serialize_sub_project(sub_project: SubProject) -> dict[str, object]:
    payload = SubProjectRead.model_validate(sub_project).model_dump(mode="json")
    payload["dept_name"] = sub_project.department.name if sub_project.department else None
    payload["main_project_name"] = (
        sub_project.main_project.name if sub_project.main_project else None
    )
    payload["manager_name"] = sub_project.manager.username if sub_project.manager else None
    payload["remaining_amount"] = str(sub_project.budget - sub_project.spent_amount)
    return payload
```

Also add optional fields to `SubProjectRead` so OpenAPI and frontend generated expectations are consistent:

```python
    dept_name: str | None = None
    main_project_name: str | None = None
    manager_name: str | None = None
    remaining_amount: Decimal | None = None
```

Add the equivalent optional fields to `MainProjectRead` if the serializer approach is used:

```python
    dept_name: str | None = None
    creator_name: str | None = None
    remaining_amount: Decimal | None = None
```

- [ ] **Step 6: Eager-load relationships in repositories**

In `backend/app/services/main_projects.py`, import `selectinload` and update list/detail queries:

```python
statement = (
    select(MainProject)
    .options(
        selectinload(MainProject.department),
        selectinload(MainProject.creator),
    )
    .order_by(MainProject.created_at.desc())
    .offset((page - 1) * page_size)
    .limit(page_size)
)
```

For `get_by_id`, use:

```python
statement = (
    select(MainProject)
    .options(
        selectinload(MainProject.department),
        selectinload(MainProject.creator),
    )
    .where(MainProject.id == project_id)
)
project = await self._session.scalar(statement)
```

In `backend/app/services/sub_projects.py`, eager-load:

```python
statement = (
    select(SubProject)
    .options(
        selectinload(SubProject.department),
        selectinload(SubProject.main_project),
        selectinload(SubProject.manager),
    )
    .where(*conditions)
    .order_by(SubProject.created_at.desc())
    .offset((page - 1) * page_size)
    .limit(page_size)
)
```

Use the same `.options(...)` pattern in `get_by_id`.

- [ ] **Step 7: Run targeted backend tests**

Run:

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_main_project_management.py tests/unit/test_sub_project_management.py
```

Expected: all tests in both files pass.

- [ ] **Step 8: Commit Task 1**

Run:

```powershell
git add backend/app/schemas/main_projects.py backend/app/schemas/sub_projects.py backend/app/api/v1/main_projects.py backend/app/api/v1/sub_projects.py backend/app/services/main_projects.py backend/app/services/sub_projects.py backend/tests/unit/test_main_project_management.py backend/tests/unit/test_sub_project_management.py
git commit -m "feat: expose project business summary fields"
```

---

## Task 2: Frontend Selectors Replace Raw Department and Main Project IDs

**Files:**

- Create: `frontend/src/components/form/DepartmentSelect.vue`
- Create: `frontend/src/components/form/MainProjectSelect.vue`
- Modify: `frontend/src/views/admin/UserEdit.vue`
- Modify: `frontend/src/views/admin/DepartmentList.vue`
- Modify: `frontend/src/views/main-project/MainProjectEdit.vue`
- Modify: `frontend/src/views/main-project/MainProjectReview.vue`
- Modify: `frontend/src/views/sub-project/SubProjectEdit.vue`
- Modify: `frontend/src/types/projects.ts`
- Test: `frontend/src/components/form/DepartmentSelect.test.ts`
- Test: `frontend/src/components/form/MainProjectSelect.test.ts`

- [ ] **Step 1: Add failing selector tests**

Create `frontend/src/components/form/DepartmentSelect.test.ts`:

```ts
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DepartmentSelect from '@/components/form/DepartmentSelect.vue';
import { useDepartmentStore } from '@/stores/useDepartmentStore';

describe('DepartmentSelect', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('loads departments and emits selected department id', async () => {
    const store = useDepartmentStore();
    store.departments = [
      { code: 'XZ', created_at: '', id: 'dept-1', name: '行政部', updated_at: '' },
    ];
    store.fetchDepartments = vi.fn().mockResolvedValue(undefined);

    const wrapper = mount(DepartmentSelect, {
      props: { modelValue: '' },
      global: { stubs: ['el-select', 'el-option'] },
    });

    await wrapper.vm.$nextTick();
    await wrapper.setValue('dept-1');

    expect(store.fetchDepartments).toHaveBeenCalled();
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['dept-1']);
    expect(wrapper.text()).toContain('行政部');
  });
});
```

Create `frontend/src/components/form/MainProjectSelect.test.ts`:

```ts
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MainProjectSelect from '@/components/form/MainProjectSelect.vue';
import { useMainProjectStore } from '@/stores/useMainProjectStore';

describe('MainProjectSelect', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('only offers approved main projects by default', async () => {
    const store = useMainProjectStore();
    store.projects = [
      {
        created_at: '',
        creator_id: 'creator-1',
        creator_name: '负责人',
        dept_id: 'dept-1',
        dept_name: '行政部',
        expected_finish_date: '2026-05-31',
        id: 'main-1',
        name: '2026办公设备升级',
        project_no: 'MP001',
        remark: null,
        remaining_amount: '500000.00',
        spent_amount: '0.00',
        status: 'not_started',
        total_budget: '500000.00',
        updated_at: '',
      },
      {
        created_at: '',
        creator_id: 'creator-2',
        dept_id: 'dept-1',
        expected_finish_date: '2026-05-31',
        id: 'main-2',
        name: '待审核项目',
        project_no: 'MP002',
        remark: null,
        spent_amount: '0.00',
        status: 'pending_review',
        total_budget: '100.00',
        updated_at: '',
      },
    ];
    store.fetchMainProjects = vi.fn().mockResolvedValue(undefined);

    const wrapper = mount(MainProjectSelect, {
      props: { modelValue: '' },
      global: { stubs: ['el-select', 'el-option'] },
    });

    expect(store.fetchMainProjects).toHaveBeenCalled();
    expect(wrapper.text()).toContain('2026办公设备升级');
    expect(wrapper.text()).not.toContain('待审核项目');
  });
});
```

- [ ] **Step 2: Run selector tests and verify they fail**

Run:

```powershell
cd C:\management\frontend
npm.cmd run test:unit -- DepartmentSelect MainProjectSelect
```

Expected: fail because both selector components do not exist.

- [ ] **Step 3: Create `DepartmentSelect.vue`**

Create `frontend/src/components/form/DepartmentSelect.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { useDepartmentStore } from '@/stores/useDepartmentStore';

const props = defineProps<{
  modelValue: string;
  placeholder?: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const departmentStore = useDepartmentStore();
const selectedValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
});

onMounted(async () => {
  await departmentStore.fetchDepartments();
});
</script>

<template>
  <el-select
    v-model="selectedValue"
    data-test="department-select"
    filterable
    :loading="departmentStore.loading"
    :placeholder="placeholder ?? '请选择责任部门'"
  >
    <el-option
      v-for="department in departmentStore.departments"
      :key="department.id"
      :label="`${department.name}（${department.code}）`"
      :value="department.id"
    />
  </el-select>
</template>
```

- [ ] **Step 4: Create `MainProjectSelect.vue`**

Create `frontend/src/components/form/MainProjectSelect.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { useMainProjectStore } from '@/stores/useMainProjectStore';
import type { MainProjectRead } from '@/types/projects';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    includeStatuses?: string[];
  }>(),
  {
    includeStatuses: () => ['not_started', 'in_progress'],
  },
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const mainProjectStore = useMainProjectStore();
const selectedValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
});

const selectableProjects = computed<MainProjectRead[]>(() =>
  mainProjectStore.projects.filter((project) => props.includeStatuses.includes(project.status)),
);

onMounted(async () => {
  await mainProjectStore.fetchMainProjects({ page: 1, pageSize: 100 });
});
</script>

<template>
  <el-select
    v-model="selectedValue"
    data-test="main-project-select"
    filterable
    :loading="mainProjectStore.loading"
    placeholder="请选择已审核主项目"
  >
    <el-option
      v-for="project in selectableProjects"
      :key="project.id"
      :label="`${project.project_no} · ${project.name}`"
      :value="project.id"
    />
  </el-select>
</template>
```

- [ ] **Step 5: Update frontend project types**

In `frontend/src/types/projects.ts`, add optional fields to `MainProjectRead`:

```ts
  creator_name?: string | null;
  dept_name?: string | null;
  remaining_amount?: string | null;
```

Add optional fields to `SubProjectRead`:

```ts
  dept_name?: string | null;
  main_project_name?: string | null;
  manager_name?: string | null;
  remaining_amount?: string | null;
```

- [ ] **Step 6: Replace department ID input in user edit**

In `frontend/src/views/admin/UserEdit.vue`, import the selector:

```ts
import DepartmentSelect from '@/components/form/DepartmentSelect.vue';
```

Replace the department form item:

```vue
<el-form-item label="部门">
  <DepartmentSelect v-model="form.deptId" placeholder="可留空，选择用户所属部门" />
</el-form-item>
```

- [ ] **Step 7: Replace department ID input in main project create/edit**

In `frontend/src/views/main-project/MainProjectEdit.vue`, import `DepartmentSelect` and replace:

```vue
<el-form-item label="责任部门" :error="errors.dept_id">
  <DepartmentSelect v-model="form.dept_id" />
</el-form-item>
```

- [ ] **Step 8: Replace department ID input in main project review**

In `frontend/src/views/main-project/MainProjectReview.vue`, import `DepartmentSelect` and replace:

```vue
<el-form-item label="责任部门">
  <DepartmentSelect v-model="form.dept_id" />
</el-form-item>
```

Update the changed-field label from `部门 ID` to `责任部门`.

- [ ] **Step 9: Replace main project and department ID inputs in sub project create/edit**

In `frontend/src/views/sub-project/SubProjectEdit.vue`, import both selectors:

```ts
import DepartmentSelect from '@/components/form/DepartmentSelect.vue';
import MainProjectSelect from '@/components/form/MainProjectSelect.vue';
```

Replace the main project form item:

```vue
<el-form-item label="关联主项目" :error="errors.main_project_id">
  <MainProjectSelect v-model="form.main_project_id" :disabled="isEditMode" />
</el-form-item>
```

If `MainProjectSelect` needs disabled support, add `disabled?: boolean` to props and bind `:disabled="disabled"` to `el-select`.

Replace department form item:

```vue
<el-form-item label="责任部门" :error="errors.dept_id">
  <DepartmentSelect v-model="form.dept_id" />
</el-form-item>
```

Add a workflow hint below the header:

```vue
<el-alert
  show-icon
  title="子项目审核通过后会自动生成立项、采购、合同、验收、财务付款、后评价 6 个环节。预算会纳入所选主项目额度校验。"
  type="info"
/>
```

- [ ] **Step 10: Show department ID in department management**

In `frontend/src/views/admin/DepartmentList.vue`, update columns:

```ts
const columns = [
  { key: 'id', label: '部门 ID', minWidth: 260 },
  { key: 'code', label: '部门编码', minWidth: 160 },
  { key: 'name', label: '部门名称', minWidth: 200 },
  { key: 'updated_at', label: '更新时间', width: 180 },
  { key: 'actions', label: '操作', width: 180 },
];
```

- [ ] **Step 11: Run frontend tests and typecheck**

Run:

```powershell
cd C:\management\frontend
npm.cmd run test:unit -- DepartmentSelect MainProjectSelect
npm.cmd run typecheck
```

Expected: selector tests pass and typecheck passes.

- [ ] **Step 12: Commit Task 2**

Run:

```powershell
git add frontend/src/components/form/DepartmentSelect.vue frontend/src/components/form/MainProjectSelect.vue frontend/src/components/form/DepartmentSelect.test.ts frontend/src/components/form/MainProjectSelect.test.ts frontend/src/views/admin/UserEdit.vue frontend/src/views/admin/DepartmentList.vue frontend/src/views/main-project/MainProjectEdit.vue frontend/src/views/main-project/MainProjectReview.vue frontend/src/views/sub-project/SubProjectEdit.vue frontend/src/types/projects.ts
git commit -m "feat: replace raw project ids with selectors"
```

---

## Task 3: Frontend Project Lists Show Flow-Relevant Business Fields

**Files:**

- Modify: `frontend/src/views/main-project/MainProjectList.vue`
- Modify: `frontend/src/views/main-project/MainProjectDetail.vue`
- Modify: `frontend/src/views/sub-project/SubProjectList.vue`
- Modify: `frontend/src/views/sub-project/SubProjectDetail.vue`
- Test: `frontend/src/views/main-project/MainProjectList.test.ts`
- Test: `frontend/src/views/sub-project/SubProjectList.test.ts`

- [ ] **Step 1: Add failing main project list test**

Create `frontend/src/views/main-project/MainProjectList.test.ts`:

```ts
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MainProjectList from '@/views/main-project/MainProjectList.vue';
import { useMainProjectStore } from '@/stores/useMainProjectStore';

describe('MainProjectList', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('shows department name, spent amount, creator name, and created date', async () => {
    const store = useMainProjectStore();
    store.projects = [
      {
        created_at: '2026-05-13T09:00:00+08:00',
        creator_id: 'user-1',
        creator_name: '综合部负责人',
        dept_id: 'dept-1',
        dept_name: '行政部',
        expected_finish_date: '2026-06-30',
        id: 'main-1',
        name: '2026办公设备升级',
        project_no: 'MP001',
        remaining_amount: '275000.00',
        remark: null,
        spent_amount: '225000.00',
        status: 'in_progress',
        total_budget: '500000.00',
        updated_at: '',
      },
    ];
    store.fetchMainProjects = vi.fn().mockResolvedValue(undefined);

    const wrapper = mount(MainProjectList, {
      global: {
        stubs: ['router-link', 'el-button', 'SearchBar', 'StatusTag'],
      },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('行政部');
    expect(wrapper.text()).toContain('225,000.00');
    expect(wrapper.text()).toContain('综合部负责人');
    expect(wrapper.text()).toContain('2026-05-13');
  });
});
```

- [ ] **Step 2: Add failing sub project list test**

Create `frontend/src/views/sub-project/SubProjectList.test.ts`:

```ts
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SubProjectList from '@/views/sub-project/SubProjectList.vue';
import { useSubProjectStore } from '@/stores/useSubProjectStore';

describe('SubProjectList', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('shows main project name, manager name, spent amount, and remaining amount', async () => {
    const store = useSubProjectStore();
    store.subProjects = [
      {
        actual_end_date: null,
        budget: '180000.00',
        created_at: '',
        creator_id: 'creator-1',
        dept_id: 'dept-1',
        dept_name: '行政部',
        id: 'sub-1',
        main_project_id: 'main-1',
        main_project_name: '2026办公设备升级',
        manager_id: 'user-1',
        manager_name: '张三',
        name: '采购高性能工作站',
        plan_end_date: '2026-06-01',
        project_no: 'SP001',
        remaining_amount: '126000.00',
        remark: null,
        spent_amount: '54000.00',
        status: 'in_progress',
        updated_at: '',
      },
    ];
    store.fetchSubProjects = vi.fn().mockResolvedValue(undefined);

    const wrapper = mount(SubProjectList, {
      global: {
        stubs: ['router-link', 'el-button', 'SearchBar', 'StatusTag'],
      },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('2026办公设备升级');
    expect(wrapper.text()).toContain('张三');
    expect(wrapper.text()).toContain('54,000.00');
    expect(wrapper.text()).toContain('126,000.00');
  });
});
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
cd C:\management\frontend
npm.cmd run test:unit -- MainProjectList SubProjectList
```

Expected: fail because current columns do not render the required fields.

- [ ] **Step 4: Update main project list columns and slots**

In `frontend/src/views/main-project/MainProjectList.vue`, replace columns with:

```ts
const columns = [
  { key: 'project_no', label: '项目编号', minWidth: 160 },
  { key: 'name', label: '项目名称', minWidth: 220 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'dept_name', label: '责任部门', minWidth: 140 },
  { key: 'total_budget', label: '总预算', width: 140 },
  { key: 'spent_amount', label: '已用金额', width: 140 },
  { key: 'remaining_amount', label: '剩余金额', width: 140 },
  { key: 'creator_name', label: '创建人', width: 140 },
  { key: 'created_at', label: '创建时间', width: 140 },
  { key: 'actions', label: '操作', width: 120 },
];
```

Add slots:

```vue
<template #dept_name="{ row }">
  {{ (row as MainProjectRead).dept_name || (row as MainProjectRead).dept_id }}
</template>
<template #spent_amount="{ value }">
  {{ formatMoney(value) }}
</template>
<template #remaining_amount="{ value }">
  {{ formatMoney(value) }}
</template>
<template #creator_name="{ row }">
  {{ (row as MainProjectRead).creator_name || (row as MainProjectRead).creator_id || '-' }}
</template>
<template #created_at="{ value }">
  {{ formatDate(value) }}
</template>
```

- [ ] **Step 5: Update sub project list columns and slots**

In `frontend/src/views/sub-project/SubProjectList.vue`, replace columns with:

```ts
const columns = [
  { key: 'project_no', label: '子项目编号', minWidth: 180 },
  { key: 'name', label: '子项目名称', minWidth: 220 },
  { key: 'status', label: '状态', width: 110 },
  { key: 'main_project_name', label: '主项目', minWidth: 180 },
  { key: 'dept_name', label: '责任部门', minWidth: 140 },
  { key: 'manager_name', label: '负责人', width: 120 },
  { key: 'budget', label: '预算', width: 140 },
  { key: 'spent_amount', label: '已用金额', width: 140 },
  { key: 'remaining_amount', label: '剩余金额', width: 140 },
  { key: 'plan_end_date', label: '计划完成', width: 140 },
  { key: 'actions', label: '操作', width: 120 },
];
```

Add corresponding slots for `main_project_name`, `dept_name`, `manager_name`, `spent_amount`, and `remaining_amount`, each falling back to the existing ID.

- [ ] **Step 6: Update detail pages to prefer names**

In `MainProjectDetail.vue`, change department and created fields:

```vue
<el-descriptions-item label="责任部门">
  {{ project.dept_name || project.dept_id }}
</el-descriptions-item>
<el-descriptions-item label="创建人">
  {{ project.creator_name || project.creator_id || '-' }}
</el-descriptions-item>
<el-descriptions-item label="创建时间">
  {{ formatDate(project.created_at) }}
</el-descriptions-item>
```

In `SubProjectDetail.vue`, prefer names:

```vue
<el-descriptions-item label="主项目">
  {{ subProject.main_project_name || subProject.main_project_id }}
</el-descriptions-item>
<el-descriptions-item label="责任部门">
  {{ subProject.dept_name || subProject.dept_id }}
</el-descriptions-item>
<el-descriptions-item label="负责人">
  {{ subProject.manager_name || subProject.manager_id }}
</el-descriptions-item>
```

- [ ] **Step 7: Run frontend tests and typecheck**

Run:

```powershell
cd C:\management\frontend
npm.cmd run test:unit -- MainProjectList SubProjectList
npm.cmd run typecheck
```

Expected: tests pass and typecheck passes.

- [ ] **Step 8: Commit Task 3**

Run:

```powershell
git add frontend/src/views/main-project/MainProjectList.vue frontend/src/views/main-project/MainProjectDetail.vue frontend/src/views/main-project/MainProjectList.test.ts frontend/src/views/sub-project/SubProjectList.vue frontend/src/views/sub-project/SubProjectDetail.vue frontend/src/views/sub-project/SubProjectList.test.ts
git commit -m "feat: show flow fields in project lists"
```

---

## Task 4: Document Display Name End-to-End

**Files:**

- Modify: `backend/app/models/documents.py`
- Modify: `backend/app/schemas/documents.py`
- Modify: `backend/app/api/v1/documents.py`
- Modify: `backend/app/services/documents.py`
- Create: `backend/alembic/versions/0037_add_document_display_name.py`
- Modify: `backend/tests/unit/test_document_models.py`
- Modify: `backend/tests/unit/test_document_upload.py`
- Modify: `frontend/src/types/documents.ts`
- Modify: `frontend/src/api/documents.ts`
- Modify: `frontend/src/components/document/DocumentUploader.vue`
- Modify: `frontend/src/components/document/DocumentList.vue`
- Modify: `frontend/src/components/document/PdfPreview.vue`
- Test: `frontend/src/components/document/DocumentList.test.ts`

- [ ] **Step 1: Add failing backend tests**

In `backend/tests/unit/test_document_models.py`, add:

```python
def test_document_read_exposes_display_name() -> None:
    document = DocumentFactory(file_name="uuid-contract.pdf")
    document.display_name = "主合同扫描件"

    payload = DocumentRead.model_validate(document).model_dump()

    assert payload["display_name"] == "主合同扫描件"
```

In `backend/tests/unit/test_document_upload.py`, add:

```python
async def test_upload_document_persists_display_name() -> None:
    service, repository, actor, sub_project, phase = make_document_service()

    document = await service.upload_document(
        actor=actor,
        sub_project_id=sub_project.id,
        phase_id=phase.id,
        doc_type="contract",
        file_name="uuid-contract.pdf",
        content=b"contract",
        display_name="主合同扫描件",
    )

    assert document.display_name == "主合同扫描件"
```

If `upload_document` uses an upload object instead of direct arguments, add `display_name="主合同扫描件"` to that object and assert on the returned document.

- [ ] **Step 2: Run backend tests and verify they fail**

Run:

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_document_models.py::test_document_read_exposes_display_name tests/unit/test_document_upload.py::test_upload_document_persists_display_name
```

Expected: fail because `display_name` is not defined.

- [ ] **Step 3: Add model field and migration**

In `backend/app/models/documents.py`, add:

```python
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
```

Place it after `file_name`.

Create `backend/alembic/versions/0037_add_document_display_name.py`:

```python
"""add document display name

Revision ID: 0037
Revises: 0036
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("display_name", sa.String(length=255), nullable=True),
    )
    op.execute("UPDATE documents SET display_name = file_name WHERE display_name IS NULL")
    op.alter_column("documents", "display_name", nullable=False)


def downgrade() -> None:
    op.drop_column("documents", "display_name")
```

- [ ] **Step 4: Update schemas and upload API**

In `backend/app/schemas/documents.py`, add:

```python
    display_name: str
```

In `backend/app/api/v1/documents.py`, add the form field:

```python
    display_name: Annotated[str | None, Form()] = None,
```

Pass it into the service call:

```python
display_name=display_name,
```

- [ ] **Step 5: Persist cleaned display name in service**

In `backend/app/services/documents.py`, add a helper:

```python
def clean_display_name(display_name: str | None, file_name: str) -> str:
    cleaned = (display_name or "").strip()
    return cleaned[:255] if cleaned else file_name[:255]
```

When constructing `Document`, set:

```python
display_name=clean_display_name(display_name, file_name),
```

- [ ] **Step 6: Add failing frontend document list test**

Create `frontend/src/components/document/DocumentList.test.ts`:

```ts
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import DocumentList from '@/components/document/DocumentList.vue';

describe('DocumentList', () => {
  it('uses display_name as the primary file title', () => {
    const wrapper = mount(DocumentList, {
      props: {
        documents: [
          {
            acceptance_step_id: null,
            created_at: '2026-05-13T09:00:00+08:00',
            display_name: '主合同扫描件',
            doc_no: 'D001',
            doc_type: 'contract',
            file_name: 'uuid-contract.pdf',
            file_size: 123,
            id: 'doc-1',
            is_deleted: false,
            is_latest: true,
            phase_id: 'phase-1',
            scan_result: null,
            scan_status: 'clean',
            scanned_at: null,
            sub_project_id: 'sub-1',
            updated_at: '',
            uploader_id: 'user-1',
            version: 1,
          },
        ],
      },
      global: { stubs: ['el-tag', 'component'] },
    });

    expect(wrapper.text()).toContain('主合同扫描件');
    expect(wrapper.text()).not.toContain('uuid-contract.pdfv1');
  });
});
```

- [ ] **Step 7: Update frontend document types and upload payload**

In `frontend/src/types/documents.ts`, add:

```ts
  display_name: string;
```

to `DocumentRead`, and:

```ts
  displayName?: string | null;
```

to `DocumentUploadPayload`.

In `frontend/src/api/documents.ts`, append:

```ts
if (payload.displayName?.trim()) {
  form.append('display_name', payload.displayName.trim());
}
```

- [ ] **Step 8: Add title input to uploader**

In `DocumentUploader.vue`, add:

```ts
const displayName = ref('');
```

Pass it in upload payload:

```ts
displayName: displayName.value.trim() || file.name,
```

After successful upload:

```ts
displayName.value = '';
```

Add template input near the file action:

```vue
<el-input
  v-model="displayName"
  data-test="document-display-name"
  placeholder="文件标题，例如：主合同扫描件"
/>
```

- [ ] **Step 9: Render display name in list and preview**

In `DocumentList.vue`, create helper:

```ts
function titleOf(document: DocumentRead): string {
  return document.display_name || document.file_name;
}
```

Replace primary title:

```vue
<strong>{{ titleOf(selectedDocument(group)) }}</strong>
```

Keep system filename in metadata:

```vue
<div>
  <dt>系统文件名</dt>
  <dd>{{ selectedDocument(group).file_name }}</dd>
</div>
```

In `PdfPreview.vue`, prefer `document.display_name` for the visible title while preserving `downloadFileName`.

- [ ] **Step 10: Run backend and frontend checks**

Run:

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_document_models.py tests/unit/test_document_upload.py
cd C:\management\frontend
npm.cmd run test:unit -- DocumentList
npm.cmd run typecheck
```

Expected: all targeted checks pass.

- [ ] **Step 11: Commit Task 4**

Run:

```powershell
git add backend/app/models/documents.py backend/app/schemas/documents.py backend/app/api/v1/documents.py backend/app/services/documents.py backend/alembic/versions/0037_add_document_display_name.py backend/tests/unit/test_document_models.py backend/tests/unit/test_document_upload.py frontend/src/types/documents.ts frontend/src/api/documents.ts frontend/src/components/document/DocumentUploader.vue frontend/src/components/document/DocumentList.vue frontend/src/components/document/PdfPreview.vue frontend/src/components/document/DocumentList.test.ts
git commit -m "feat: add document display names"
```

---

## Task 5: Procurement Type Selection and Inquiry Three-Quote Rule

**Files:**

- Modify: `backend/app/schemas/phases.py`
- Modify: `backend/app/api/v1/phases.py`
- Modify: `backend/app/services/phases.py`
- Modify: `backend/app/seeds/phase_doc_templates.py`
- Modify: `backend/app/seeds/workflow_templates.py`
- Modify: `backend/tests/unit/test_phase_promote.py`
- Modify: `frontend/src/types/phases.ts`
- Modify: `frontend/src/api/phases.ts`
- Modify: `frontend/src/stores/usePhaseStore.ts`
- Modify: `frontend/src/components/phase/PhaseDocumentPanel.vue`

- [ ] **Step 1: Add failing backend test for procurement type update**

In `backend/tests/unit/test_phase_promote.py`, add:

```python
async def test_update_procurement_type_only_allows_procurement_phase() -> None:
    leader, sub_project = make_leader_and_sub_project()
    phase = make_phase(sub_project, 2, PhaseStatus.in_progress, procurement_type=None)
    repository = InMemoryPhaseRepository(phases=[phase], sub_projects=[sub_project])
    service = PhaseService(repository=repository)

    updated = await service.update_procurement_type(
        actor=leader,
        phase_id=phase.id,
        procurement_type=ProcurementType.inquiry,
    )

    assert updated.procurement_type == ProcurementType.inquiry
```

- [ ] **Step 2: Add failing backend test for inquiry three quotes**

In `backend/tests/unit/test_phase_promote.py`, add:

```python
async def test_promote_inquiry_procurement_requires_three_supplier_quotes() -> None:
    leader, sub_project = make_leader_and_sub_project()
    phase1 = make_phase(sub_project, 1, PhaseStatus.completed)
    phase2 = make_phase(
        sub_project,
        2,
        PhaseStatus.in_progress,
        procurement_type=ProcurementType.inquiry,
    )
    repository = InMemoryPhaseRepository(
        phases=[phase1, phase2],
        sub_projects=[sub_project],
        templates=[
            make_template(2, "oa_screenshot", "=1"),
            make_template(2, "supplier_quote", ">=3", procurement_type=ProcurementType.inquiry),
        ],
        documents=[
            make_document(sub_project, phase2, "oa_screenshot"),
            make_document(sub_project, phase2, "supplier_quote"),
            make_document(sub_project, phase2, "supplier_quote"),
        ],
    )
    service = PhaseService(repository=repository)

    with pytest.raises(BusinessException) as exc_info:
        await service.promote_phase(actor=leader, phase_id=phase2.id)

    assert exc_info.value.code == 3002
    assert exc_info.value.data["missing_documents"] == [
        {"doc_type": "supplier_quote", "required": ">=3", "actual": 2},
    ]
```

Use existing helper names from `test_phase_promote.py`; if the file uses different names, adapt this test to the existing helper signatures and keep the same assertion.

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_phase_promote.py::test_update_procurement_type_only_allows_procurement_phase tests/unit/test_phase_promote.py::test_promote_inquiry_procurement_requires_three_supplier_quotes
```

Expected: fail because update endpoint/service and `supplier_quote >=3` rule are not implemented.

- [ ] **Step 4: Add phase update schema**

In `backend/app/schemas/phases.py`, add:

```python
class PhaseProcurementTypeUpdate(BaseModel):
    procurement_type: ProcurementType

    model_config = ConfigDict(extra="forbid")
```

- [ ] **Step 5: Add service method**

In `backend/app/services/phases.py`, add:

```python
    async def update_procurement_type(
        self,
        *,
        actor: User,
        phase_id: UUID,
        procurement_type: ProcurementType,
    ) -> Phase:
        phase = await self._get_existing_phase(phase_id)
        sub_project = await self._get_existing_sub_project(phase.sub_project_id)
        self._ensure_can_promote(actor, sub_project)
        if phase.phase_no != 2:
            raise BusinessException(
                code=3003,
                message="Procurement type can only be set on procurement phase",
                status_code=409,
                data={"phase_no": phase.phase_no},
            )
        if phase.status == PhaseStatus.completed:
            raise BusinessException(
                code=3003,
                message="Completed procurement phase cannot change procurement type",
                status_code=409,
                data={"status": phase.status.value},
            )
        phase.procurement_type = procurement_type
        phase.updated_at = datetime.now(UTC)
        await self._repository.commit()
        await self._repository.refresh_phase(phase)
        return phase
```

If `PhaseRepository` does not yet expose `commit` and `refresh_phase`, add them to the protocol and both repository implementations using existing commit/refresh patterns from adjacent services.

- [ ] **Step 6: Add API endpoint**

In `backend/app/api/v1/phases.py`, import `PhaseProcurementTypeUpdate` and add:

```python
@router.put("/{phase_id}/procurement-type")
async def update_procurement_type(
    phase_id: UUID,
    payload: PhaseProcurementTypeUpdate,
    service: Annotated[PhaseService, Depends(get_phase_service)],
    current_user: Annotated[User, Depends(require_permission("phase.promote"))],
) -> dict[str, object]:
    phase = await service.update_procurement_type(
        actor=current_user,
        phase_id=phase_id,
        procurement_type=payload.procurement_type,
    )
    return success_response(serialize_phase(phase))
```

- [ ] **Step 7: Change inquiry template to three supplier quotes**

In `backend/app/seeds/phase_doc_templates.py`, replace the inquiry row:

```python
PhaseDocTemplateSeed(
    2,
    "supplier_quote",
    PhaseDocRequirement.conditional,
    ">=3",
    ProcurementType.inquiry,
),
```

Keep `oa_screenshot` as required. Remove or stop seeding `inquiry_report` as the required inquiry gate for new installs. If old databases already have `inquiry_report`, add a small migration only if production data needs automatic template conversion; for current development seed flow, updating seed and workflow snapshot builder is enough.

- [ ] **Step 8: Add frontend API/store support**

In `frontend/src/api/phases.ts`, add:

```ts
export async function updateProcurementType(
  phaseId: string,
  procurementType: ProcurementType,
): Promise<PhaseRead> {
  const response = await client.put<ApiResponse<PhaseRead>>(
    `/phases/${phaseId}/procurement-type`,
    { procurement_type: procurementType },
  );
  return response.data.data;
}
```

In `frontend/src/stores/usePhaseStore.ts`, add an action:

```ts
async updateProcurementType(phaseId: string, procurementType: ProcurementType) {
  const phase = await updateProcurementTypeRequest(phaseId, procurementType);
  this.upsertPhase(phase);
  if (this.currentPhase?.id === phase.id) {
    this.currentPhase = phase;
  }
  return phase;
}
```

Use the store's existing phase list update helper; if none exists, replace the matching `this.phases` item by id.

- [ ] **Step 9: Add procurement selector to phase document panel**

In `PhaseDocumentPanel.vue`, for phase 2 render:

```vue
<el-form-item v-if="detail.phase_no === 2" label="采购类型">
  <el-select
    :model-value="detail.procurement_type"
    data-test="procurement-type-select"
    placeholder="请选择采购类型"
    @update:model-value="updateProcurementType"
  >
    <el-option label="询价类" value="inquiry" />
    <el-option label="招标类" value="bidding" />
    <el-option label="单一来源" value="single_source" />
  </el-select>
</el-form-item>
```

Add script function:

```ts
async function updateProcurementType(value: ProcurementType): Promise<void> {
  if (!detail.value) {
    return;
  }
  await phaseStore.updateProcurementType(detail.value.id, value);
  await loadSelectedPhase();
}
```

Import `ProcurementType`.

- [ ] **Step 10: Run targeted checks**

Run:

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_phase_promote.py
cd C:\management\frontend
npm.cmd run typecheck
```

Expected: backend phase tests pass and frontend typecheck passes.

- [ ] **Step 11: Commit Task 5**

Run:

```powershell
git add backend/app/schemas/phases.py backend/app/api/v1/phases.py backend/app/services/phases.py backend/app/seeds/phase_doc_templates.py backend/app/seeds/workflow_templates.py backend/tests/unit/test_phase_promote.py frontend/src/types/phases.ts frontend/src/api/phases.ts frontend/src/stores/usePhaseStore.ts frontend/src/components/phase/PhaseDocumentPanel.vue
git commit -m "feat: enforce procurement type document gates"
```

---

## Task 6: Phase Document Panel Owns Promotion Action and Blocker Messaging

**Files:**

- Modify: `frontend/src/components/phase/PhaseDocumentPanel.vue`
- Modify: `frontend/src/components/phase/PhaseProgress.vue`
- Modify: `frontend/src/views/sub-project/SubProjectDetail.vue`
- Test: `frontend/src/components/phase/PhaseDocumentPanel.test.ts`

- [ ] **Step 1: Add failing frontend test**

Create `frontend/src/components/phase/PhaseDocumentPanel.test.ts`:

```ts
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PhaseDocumentPanel from '@/components/phase/PhaseDocumentPanel.vue';
import { usePhaseStore } from '@/stores/usePhaseStore';

describe('PhaseDocumentPanel', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('shows promote blocker when required documents are missing', async () => {
    const store = usePhaseStore();
    store.phases = [
      {
        code: 'initiation',
        created_at: '',
        enter_at: '2026-05-15T09:00:00+08:00',
        finish_at: null,
        id: 'phase-1',
        name: '立项',
        phase_no: 1,
        procurement_type: null,
        status: 'in_progress',
        sub_project_id: 'sub-1',
        updated_at: '',
      },
    ];
    store.fetchPhases = vi.fn().mockResolvedValue(undefined);
    store.fetchPhaseDetail = vi.fn().mockResolvedValue({
      ...store.phases[0],
      completion: {
        missing_doc_types: ['meeting_material'],
        required_total: 2,
        uploaded_total: 1,
      },
      required_documents: [
        {
          doc_type: 'meeting_material',
          procurement_type: null,
          qty_rule: '=1',
          requirement: 'required',
        },
      ],
      uploaded_documents: [],
    });

    const wrapper = mount(PhaseDocumentPanel, {
      props: { subProjectId: 'sub-1' },
      global: { stubs: ['DocumentUploader', 'DocumentList', 'el-tag', 'el-button'] },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('缺少材料：meeting_material');
    expect(wrapper.text()).toContain('暂不能推进');
  });
});
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
cd C:\management\frontend
npm.cmd run test:unit -- PhaseDocumentPanel
```

Expected: fail because blocker messaging is absent.

- [ ] **Step 3: Add blocker state and promote action**

In `PhaseDocumentPanel.vue`, add computed values:

```ts
const canPromoteSelectedPhase = computed(
  () =>
    Boolean(detail.value) &&
    detail.value.status === 'in_progress' &&
    missingDocTypes.value.size === 0,
);

const promoteBlockerText = computed(() => {
  if (!detail.value) {
    return '';
  }
  if (detail.value.status !== 'in_progress') {
    return '当前环节不在进行中，暂不能推进';
  }
  if (missingDocTypes.value.size > 0) {
    return `缺少材料：${[...missingDocTypes.value].join('、')}`;
  }
  return '';
});
```

Add promote function:

```ts
async function promoteSelectedPhase(): Promise<void> {
  if (!detail.value || !canPromoteSelectedPhase.value) {
    return;
  }
  await phaseStore.promotePhase(detail.value.id);
  await initialize();
}
```

- [ ] **Step 4: Add template action**

In `PhaseDocumentPanel.vue`, under completion text add:

```vue
<div class="phase-document-panel__promote">
  <el-alert
    v-if="promoteBlockerText"
    show-icon
    :title="promoteBlockerText"
    type="warning"
  />
  <el-button
    data-test="promote-selected-phase"
    :disabled="!canPromoteSelectedPhase"
    :loading="detail ? phaseStore.promotingId === detail.id : false"
    type="primary"
    @click="promoteSelectedPhase"
  >
    {{ canPromoteSelectedPhase ? '推进环节' : '暂不能推进' }}
  </el-button>
</div>
```

- [ ] **Step 5: Keep PhaseProgress as overview-only**

In `PhaseProgress.vue`, keep the current promote button for quick action if desired, but change copy so users know the document panel is the guided path:

```vue
<p>需要查看缺失材料时，请在下方环节材料区处理并推进。</p>
```

If duplicate promote buttons confuse the UI, remove the `el-button` from `PhaseProgress.vue` and rely on `PhaseDocumentPanel.vue`.

- [ ] **Step 6: Run checks**

Run:

```powershell
cd C:\management\frontend
npm.cmd run test:unit -- PhaseDocumentPanel
npm.cmd run typecheck
```

Expected: test and typecheck pass.

- [ ] **Step 7: Commit Task 6**

Run:

```powershell
git add frontend/src/components/phase/PhaseDocumentPanel.vue frontend/src/components/phase/PhaseProgress.vue frontend/src/views/sub-project/SubProjectDetail.vue frontend/src/components/phase/PhaseDocumentPanel.test.ts
git commit -m "feat: guide phase promotion from document panel"
```

---

## Task 7: P0 Regression Pass and Documentation Update

**Files:**

- Modify: `docs/V2_ISSUE_VALIDATION_REPORT.md`
- Modify: `docs/V2_FLOW_DRIVEN_REFACTOR_SPEC.md`
- Modify: `docs/业务使用手册.md`
- Modify: `docs/管理员与运维手册.md`

- [ ] **Step 1: Run backend validation**

Run:

```powershell
cd C:\management\backend
python -B -m pytest -q --no-cov tests/unit/test_main_project_management.py tests/unit/test_sub_project_management.py tests/unit/test_document_models.py tests/unit/test_document_upload.py tests/unit/test_phase_promote.py tests/unit/test_acceptance_steps.py tests/unit/test_payment_create.py
python -B -m ruff check .
python -B -m mypy app tests
python -B -m compileall -q app tests alembic
```

Expected: all commands exit 0. If `pytest` without Docker-backed e2e is required, keep `--no-cov` targeted unit scope here and record Docker e2e as blocked only if Docker is still unavailable.

- [ ] **Step 2: Run frontend validation**

Run:

```powershell
cd C:\management\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test:unit
npm.cmd run build
```

Expected: all commands exit 0.

- [ ] **Step 3: Update validation report**

In `docs/V2_ISSUE_VALIDATION_REPORT.md`, add a new section after "修订后的优先级建议":

```markdown
## 5. P0 修复验证记录

2026-05-13 P0 实施后，以下项目已完成：

1. 部门、主项目、子项目相关 ID 输入已改为业务下拉。
2. 主项目和子项目列表已展示业务名称、金额和创建信息。
3. 子项目创建页已增加流程引导。
4. 环节材料面板已提供推进按钮和缺失材料阻断提示。
5. 采购类型已支持选择，询价类报价单按 3 份校验。
6. 附件已支持 `display_name` 并优先显示中文标题。

验证命令结果：

- Backend targeted unit checks: include each command from Step 1, its exit code, and the final pytest summary line.
- Backend lint/type/compile checks: include each command from Step 1, its exit code, and the final success or error line.
- Frontend lint/type/unit/build checks: include each command from Step 2, its exit code, and the final success or error line.
```

- [ ] **Step 4: Update business user manual**

In `docs/业务使用手册.md`, add short sections covering:

```markdown
### 创建主项目

创建主项目时选择“责任部门”，无需填写部门 ID。保存并提交审核后，审核通过的主项目才能承载子项目。

### 创建子项目

创建子项目时选择已审核主项目和责任部门。审核通过后，系统自动生成立项、采购、合同签订、验收、财务付款、后评价 6 个环节。

### 采购环节

采购环节需要先选择采购类型。询价类必须上传 3 家供应商报价单，否则不能推进到合同环节。

### 附件标题

上传附件时填写文件标题。列表优先显示标题，系统文件名保留在详情中用于排查。
```

- [ ] **Step 5: Update admin manual**

In `docs/管理员与运维手册.md`, add:

```markdown
### 部门 ID 排查

普通业务页面使用部门名称和下拉选择。管理员如需排查数据，可在“部门管理”列表查看部门 ID。

### V2 P0 回归检查

每次发布前需验证：部门下拉、主项目下拉、采购类型、询价三家报价校验、附件标题展示、环节材料面板推进按钮。
```

- [ ] **Step 6: Final git status check**

Run:

```powershell
cd C:\management
git status --short
```

Expected: only intended P0 code, test, migration, and doc files are modified.

- [ ] **Step 7: Commit Task 7**

Run:

```powershell
git add docs/V2_ISSUE_VALIDATION_REPORT.md docs/V2_FLOW_DRIVEN_REFACTOR_SPEC.md docs/业务使用手册.md docs/管理员与运维手册.md
git commit -m "docs: record v2 p0 flow validation"
```

---

## Final Verification

After all tasks are complete, run:

```powershell
cd C:\management\backend
python -B -m pytest -q
python -B -m ruff check .
python -B -m mypy app tests
python -B -m compileall -q app tests alembic
cd C:\management\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test:unit
npm.cmd run build
cd C:\management
git status --short
```

Expected:

- Backend pytest passes. If Docker/Testcontainers is unavailable, record the exact Docker error and rerun all non-Docker unit checks with `--no-cov`.
- Backend ruff, mypy, and compileall exit 0.
- Frontend lint, typecheck, unit tests, and build exit 0.
- Git status contains only intentional files if final docs are still unstaged, or is clean after final commit.

---

## Self-Review Notes

- `spent_amount` recalculation is not part of this plan because targeted unit tests already passed.
- Acceptance-step creation and acceptance-step document association are not rebuilt because targeted tests already passed.
- The plan starts with business names/selectors because those unblock the earliest user journey.
- The document `display_name` task is isolated because it requires a database migration.
- Procurement type is isolated because it changes backend phase rules and frontend phase controls together.
- Docker-backed e2e remains a separate environment validation item because current host Docker pipe was unavailable during validation.
