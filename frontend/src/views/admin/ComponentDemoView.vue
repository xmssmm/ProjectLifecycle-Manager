<script setup lang="ts">
import { ref } from 'vue';

import { ConfirmDialog, DataTable, SearchBar, StatusTag } from '@/components/common';
import PermissionGate from '@/components/permission/PermissionGate.vue';

const filters = ref({ keyword: '', status: '' });
const confirmVisible = ref(false);

const columns = [
  { key: 'name', label: '名称', minWidth: 160 },
  { key: 'status', label: '状态', width: 120 },
];

const rows = [
  { id: '1', name: '主项目 A', status: 'pending_review' },
  { id: '2', name: '子项目 B', status: 'approved' },
];

const searchFields = [
  { key: 'keyword', label: '关键字', placeholder: '项目名称', type: 'text' as const },
  {
    key: 'status',
    label: '状态',
    options: [
      { label: '待审核', value: 'pending_review' },
      { label: '已通过', value: 'approved' },
    ],
    type: 'select' as const,
  },
];
</script>

<template>
  <section class="component-demo">
    <h2>组件演示</h2>

    <SearchBar v-model="filters" :fields="searchFields" />

    <div class="component-demo__status">
      <StatusTag status="pending_review" />
      <StatusTag status="approved" />
      <PermissionGate permission="user.manage">
        <el-button type="primary" @click="confirmVisible = true"> 打开确认 </el-button>
      </PermissionGate>
    </div>

    <DataTable :columns="columns" :page="1" :page-size="20" :rows="rows" :total="rows.length">
      <template #status="{ value }">
        <StatusTag :status="String(value)" />
      </template>
    </DataTable>

    <ConfirmDialog v-model="confirmVisible" message="确认执行这个敏感操作？" title="操作确认" />
  </section>
</template>
