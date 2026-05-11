<script setup lang="ts">
import { Check, CopyDocument, Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive } from 'vue';

import { DataTable } from '@/components/common';
import { useProjectTemplateStore } from '@/stores/useProjectTemplateStore';
import type { ProjectTemplateRead, ProjectTemplateScope } from '@/types/projectTemplates';

const store = useProjectTemplateStore();
const form = reactive({
  categoryId: '',
  copyDocumentRequirements: true,
  copyPhasePlan: true,
  copyTaskChecklist: true,
  description: '',
  name: '',
  scope: 'department' as ProjectTemplateScope,
  sourceProjectId: '',
  tagId: '',
});

const templateRows = computed(() => store.templates as unknown as Record<string, unknown>[]);
const columns = [
  { key: 'name', label: '模板', minWidth: 180 },
  { key: 'source_project_no', label: '来源项目', width: 150 },
  { key: 'scope', label: '范围', width: 110 },
  { key: 'tags', label: '标签', minWidth: 180 },
  { key: 'actions', label: '操作', width: 120 },
];

onMounted(async () => {
  await store.fetchAll();
});

async function createTemplate(): Promise<void> {
  if (!form.name.trim() || !form.sourceProjectId.trim()) {
    return;
  }
  await store.createTemplate({
    category_id: form.categoryId || null,
    copy_document_requirements: form.copyDocumentRequirements,
    copy_phase_plan: form.copyPhasePlan,
    copy_task_checklist: form.copyTaskChecklist,
    description: form.description.trim() || null,
    name: form.name.trim(),
    scope: form.scope,
    source_project_id: form.sourceProjectId.trim(),
    tag_ids: form.tagId ? [form.tagId] : [],
  });
  ElMessage.success('模板已创建');
}

async function instantiateTemplate(row: unknown): Promise<void> {
  const template = asTemplate(row);
  await store.instantiateTemplate(template.id, {
    dept_id: template.owner_dept_id,
    name: `${template.name} 项目`,
  });
  ElMessage.success('项目已创建');
}

function asTemplate(row: unknown): ProjectTemplateRead {
  return row as ProjectTemplateRead;
}

function tagNames(row: unknown): string[] {
  const template = asTemplate(row);
  return template.tag_ids
    .map((tagId) => store.tags.find((tag) => tag.id === tagId)?.name)
    .filter((name): name is string => Boolean(name));
}
</script>

<template>
  <section class="admin-page template-library">
    <div class="admin-page__header">
      <div>
        <h2>项目模板库</h2>
        <p>沉淀已完成项目的字段、流程快照和任务清单。</p>
      </div>
      <el-button :icon="Refresh" :loading="store.loading" @click="store.fetchAll()">刷新</el-button>
    </div>

    <section class="template-library__taxonomy">
      <el-tag v-for="category in store.categories" :key="category.id">{{ category.name }}</el-tag>
      <el-tag v-for="tag in store.tags" :key="tag.id">{{ tag.name }}</el-tag>
    </section>

    <section class="template-library__builder">
      <el-form>
        <div class="template-library__form-grid">
          <el-form-item label="来源项目 ID">
            <el-input v-model="form.sourceProjectId" data-test="template-source-project" />
          </el-form-item>
          <el-form-item label="模板名称">
            <el-input v-model="form.name" data-test="template-name" />
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="form.categoryId">
              <el-option label="未分类" value="" />
              <el-option
                v-for="category in store.categories"
                :key="category.id"
                :label="category.name"
                :value="category.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="标签">
            <el-select v-model="form.tagId">
              <el-option label="无标签" value="" />
              <el-option
                v-for="tag in store.tags"
                :key="tag.id"
                :label="tag.name"
                :value="tag.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="范围">
            <el-select v-model="form.scope">
              <el-option label="私有" value="private" />
              <el-option label="部门" value="department" />
              <el-option label="全局" value="global" />
            </el-select>
          </el-form-item>
        </div>
        <div class="template-library__switches">
          <el-checkbox v-model="form.copyPhasePlan" label="复制流程快照" />
          <el-checkbox v-model="form.copyDocumentRequirements" label="复制文档要求" />
          <el-checkbox v-model="form.copyTaskChecklist" label="复制任务清单" />
          <el-button
            data-test="create-template"
            :disabled="!form.name.trim() || !form.sourceProjectId.trim()"
            :icon="Check"
            type="primary"
            @click="createTemplate"
          >
            创建模板
          </el-button>
        </div>
      </el-form>
    </section>

    <section class="template-library__list">
      <DataTable
        :columns="columns"
        :loading="store.loading"
        :page="1"
        :page-size="store.templates.length || 1"
        :rows="templateRows"
        :total="store.templates.length"
      >
        <template #tags="{ row }">
          <el-tag v-for="tagName in tagNames(row)" :key="tagName">{{ tagName }}</el-tag>
        </template>
        <template #actions="{ row }">
          <el-button
            data-test="instantiate-template"
            :icon="CopyDocument"
            size="small"
            @click="instantiateTemplate(row)"
          />
        </template>
      </DataTable>
    </section>
  </section>
</template>

<style scoped>
.template-library {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.template-library__taxonomy,
.template-library__switches {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.template-library__builder,
.template-library__list {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 18px;
}

.template-library__form-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
}

@media (width <= 1100px) {
  .template-library__form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
