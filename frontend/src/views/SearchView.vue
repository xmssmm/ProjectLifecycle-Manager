<script setup lang="ts">
import { Search } from '@element-plus/icons-vue';
import { ref } from 'vue';

import { useSearchStore } from '@/stores/useSearchStore';

const searchStore = useSearchStore();
const query = ref(searchStore.query);

async function submitSearch(): Promise<void> {
  if (searchStore.loading) {
    return;
  }
  await searchStore.search(query.value);
}
</script>

<template>
  <section class="admin-page search-page">
    <div class="admin-page__header">
      <div>
        <h2>全文检索</h2>
        <p>检索已通过安全扫描的项目文档内容。</p>
      </div>
    </div>

    <form class="search-page__bar" @submit.prevent="submitSearch">
      <el-input
        v-model="query"
        clearable
        data-test="search-query"
        placeholder="输入关键词"
      />
      <el-button
        data-test="submit-search"
        :icon="Search"
        :loading="searchStore.loading"
        type="primary"
        @click="submitSearch"
      >
        搜索
      </el-button>
    </form>

    <section class="search-page__results">
      <article
        v-for="item in searchStore.items"
        :key="item.document_id"
        class="search-result"
      >
        <div class="search-result__title">
          <strong>{{ item.file_name }}</strong>
          <el-tag>{{ item.doc_type }}</el-tag>
        </div>
        <p class="search-result__context">
          {{ item.sub_project_no }} · {{ item.sub_project_name }} · {{ item.phase_name }}
        </p>
        <p class="search-result__snippet">{{ item.snippet }}</p>
      </article>
    </section>
  </section>
</template>

<style scoped>
.search-page__bar {
  align-items: center;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
  margin-bottom: 20px;
}

.search-page__results {
  display: grid;
  gap: 12px;
}

.search-result {
  background: #fff;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  padding: 14px 16px;
}

.search-result__title {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.search-result__context {
  color: #64748b;
  margin: 8px 0;
}

.search-result__snippet {
  color: #0f172a;
  line-height: 1.6;
  margin: 0;
  overflow-wrap: anywhere;
}

@media (width <= 720px) {
  .search-page__bar {
    grid-template-columns: 1fr;
  }
}
</style>
