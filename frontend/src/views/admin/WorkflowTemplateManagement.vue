<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';

import { DataTable, StatusTag } from '@/components/common';
import { useWorkflowStore } from '@/stores/useWorkflowStore';
import type { WorkflowTemplateRead, WorkflowTemplateVersionRead } from '@/types/workflows';

const workflowStore = useWorkflowStore();

const projectTypeDialogVisible = ref(false);
const templateDialogVisible = ref(false);
const phaseEditorVisible = ref(false);
const validationMessage = ref('');
const selectedVersion = ref<WorkflowTemplateVersionRead | null>(null);
const phaseDefinitionsJson = ref('');

const projectTypeForm = reactive({
  code: '',
  description: '',
  name: '',
});

const templateForm = reactive({
  description: '',
  name: '',
  projectTypeId: '',
});

const projectTypeRows = computed(
  () => workflowStore.projectTypes as unknown as Record<string, unknown>[],
);
const templateRows = computed(() => workflowStore.templates as unknown as Record<string, unknown>[]);

const projectTypeColumns = [
  { key: 'name', label: '项目类型', minWidth: 160 },
  { key: 'code', label: '编码', width: 160 },
  { key: 'description', label: '说明', minWidth: 220 },
  { key: 'is_active', label: '状态', width: 120 },
];

const templateColumns = [
  { key: 'name', label: '模板', minWidth: 180 },
  { key: 'project_type_id', label: '项目类型', width: 160 },
  { key: 'status', label: '状态', width: 120 },
  { key: 'versions', label: '版本', minWidth: 220 },
  { key: 'actions', label: '操作', width: 220 },
];

onMounted(async () => {
  await workflowStore.fetchAll();
});

function openProjectTypeDialog(): void {
  projectTypeForm.code = '';
  projectTypeForm.description = '';
  projectTypeForm.name = '';
  validationMessage.value = '';
  projectTypeDialogVisible.value = true;
}

function openTemplateDialog(): void {
  templateForm.description = '';
  templateForm.name = '';
  templateForm.projectTypeId = workflowStore.projectTypes[0]?.id ?? '';
  validationMessage.value = '';
  templateDialogVisible.value = true;
}

async function submitProjectType(): Promise<void> {
  validationMessage.value = '';
  if (!projectTypeForm.code.trim() || !projectTypeForm.name.trim()) {
    validationMessage.value = '请输入项目类型编码和名称';
    return;
  }
  await workflowStore.createProjectType({
    code: projectTypeForm.code.trim(),
    description: projectTypeForm.description.trim() || null,
    name: projectTypeForm.name.trim(),
  });
  projectTypeDialogVisible.value = false;
  ElMessage.success('项目类型已创建');
}

async function submitTemplate(): Promise<void> {
  validationMessage.value = '';
  if (!templateForm.projectTypeId || !templateForm.name.trim()) {
    validationMessage.value = '请选择项目类型并输入模板名称';
    return;
  }
  await workflowStore.createTemplate({
    description: templateForm.description.trim() || null,
    name: templateForm.name.trim(),
    projectTypeId: templateForm.projectTypeId,
  });
  templateDialogVisible.value = false;
  ElMessage.success('工作流模板草稿已创建');
}

function latestVersion(template: WorkflowTemplateRead): WorkflowTemplateVersionRead | null {
  return [...template.versions].sort((a, b) => b.version_no - a.version_no)[0] ?? null;
}

function openPhaseEditor(template: WorkflowTemplateRead): void {
  const version = latestVersion(template);
  if (!version) {
    return;
  }
  selectedVersion.value = version;
  phaseDefinitionsJson.value = JSON.stringify(version.phase_definitions, null, 2);
  phaseEditorVisible.value = true;
}

async function savePhaseDefinitions(): Promise<void> {
  if (!selectedVersion.value) {
    return;
  }
  const parsed = JSON.parse(phaseDefinitionsJson.value) as WorkflowTemplateVersionRead['phase_definitions'];
  await workflowStore.updatePhaseDefinitions(selectedVersion.value.id, parsed);
  phaseEditorVisible.value = false;
  ElMessage.success('环节定义已保存');
}

async function publishLatestVersion(template: WorkflowTemplateRead): Promise<void> {
  const version = latestVersion(template);
  if (!version) {
    return;
  }
  await workflowStore.publishVersion(version.id);
  ElMessage.success('模板版本已发布');
}

function projectTypeName(projectTypeId: string): string {
  return workflowStore.projectTypes.find((item) => item.id === projectTypeId)?.name ?? projectTypeId;
}
</script>

<template>
  <section class="admin-page workflow-page">
    <div class="admin-page__header">
      <div>
        <h2>工作流模板</h2>
        <p>管理项目类型、流程模板和版本化环节定义。</p>
      </div>
      <div class="workflow-page__actions">
        <el-button data-test="open-create-project-type" @click="openProjectTypeDialog">
          新建项目类型
        </el-button>
        <el-button type="primary" @click="openTemplateDialog">新建模板</el-button>
      </div>
    </div>

    <section class="admin-page__section">
      <h3>项目类型</h3>
      <DataTable
        :columns="projectTypeColumns"
        :loading="workflowStore.loading"
        :page="1"
        :page-size="workflowStore.projectTypes.length || 1"
        :rows="projectTypeRows"
        :total="workflowStore.projectTypes.length"
      >
        <template #is_active="{ value }">
          <StatusTag :status="value ? 'active' : 'disabled'" />
        </template>
      </DataTable>
    </section>

    <section class="admin-page__section">
      <h3>流程模板</h3>
      <DataTable
        :columns="templateColumns"
        :loading="workflowStore.loading"
        :page="1"
        :page-size="workflowStore.templates.length || 1"
        :rows="templateRows"
        :total="workflowStore.templates.length"
      >
        <template #project_type_id="{ value }">
          {{ projectTypeName(String(value)) }}
        </template>
        <template #status="{ value }">
          <StatusTag :status="String(value)" />
        </template>
        <template #versions="{ row }">
          <el-tag
            v-for="version in (row as WorkflowTemplateRead).versions"
            :key="version.id"
            class="workflow-version-tag"
          >
            v{{ version.version_no }} {{ version.status }}
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button size="small" @click="openPhaseEditor(row as WorkflowTemplateRead)">
            编辑环节
          </el-button>
          <el-button
            data-test="publish-template-version"
            size="small"
            type="primary"
            @click="publishLatestVersion(row as WorkflowTemplateRead)"
          >
            发布
          </el-button>
        </template>
      </DataTable>
    </section>

    <el-dialog v-model="projectTypeDialogVisible" title="新建项目类型" width="520px">
      <el-form label-width="96px">
        <el-form-item label="编码">
          <el-input v-model="projectTypeForm.code" data-test="project-type-code" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="projectTypeForm.name" data-test="project-type-name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="projectTypeForm.description" data-test="project-type-description" />
        </el-form-item>
      </el-form>
      <p v-if="validationMessage" class="form-error">{{ validationMessage }}</p>
      <template #footer>
        <el-button @click="projectTypeDialogVisible = false">取消</el-button>
        <el-button
          data-test="submit-project-type"
          :loading="workflowStore.submitting"
          type="primary"
          @click="submitProjectType"
        >
          创建
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="templateDialogVisible" title="新建工作流模板" width="560px">
      <el-form label-width="96px">
        <el-form-item label="项目类型">
          <el-select v-model="templateForm.projectTypeId">
            <el-option
              v-for="projectType in workflowStore.projectTypes"
              :key="projectType.id"
              :label="projectType.name"
              :value="projectType.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模板名称">
          <el-input v-model="templateForm.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="templateForm.description" />
        </el-form-item>
      </el-form>
      <p v-if="validationMessage" class="form-error">{{ validationMessage }}</p>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button :loading="workflowStore.submitting" type="primary" @click="submitTemplate">
          创建
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="phaseEditorVisible" title="环节定义 JSON" width="720px">
      <el-input v-model="phaseDefinitionsJson" :rows="16" type="textarea" />
      <template #footer>
        <el-button @click="phaseEditorVisible = false">取消</el-button>
        <el-button :loading="workflowStore.submitting" type="primary" @click="savePhaseDefinitions">
          保存
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
