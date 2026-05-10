<script setup lang="ts">
interface TableColumn {
  key: string;
  label: string;
  minWidth?: number | string;
  sortable?: boolean | 'custom';
  width?: number | string;
}

defineProps<{
  columns: TableColumn[];
  loading?: boolean;
  page: number;
  pageSize: number;
  rows: Record<string, unknown>[];
  total: number;
}>();

const emit = defineEmits<{
  'sort-change': [value: unknown];
  'update:page': [value: number];
  'update:pageSize': [value: number];
}>();
</script>

<template>
  <div class="data-table">
    <el-table v-loading="loading" :data="rows" @sort-change="emit('sort-change', $event)">
      <el-table-column
        v-for="column in columns"
        :key="column.key"
        :label="column.label"
        :min-width="column.minWidth"
        :prop="column.key"
        :sortable="column.sortable"
        :width="column.width"
      >
        <template #default="{ row }">
          <slot :name="column.key" :row="row" :value="row[column.key]">
            {{ row[column.key] }}
          </slot>
        </template>
      </el-table-column>
    </el-table>

    <div class="data-table__pagination">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="emit('update:page', $event)"
        @size-change="emit('update:pageSize', $event)"
      />
    </div>
  </div>
</template>
