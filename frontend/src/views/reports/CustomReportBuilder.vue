<script setup lang="ts">
import { Check, CopyDocument, Delete, EditPen, Refresh, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';

import { DataTable } from '@/components/common';
import ReportChartPreview from '@/components/reports/ReportChartPreview.vue';
import { useAuthStore } from '@/stores/useAuthStore';
import { useCustomReportStore } from '@/stores/useCustomReportStore';
import type {
  CustomReportChartType,
  CustomReportDefinitionRead,
  CustomReportScheduleFrequency,
  CustomReportShareScope,
  DatasetAggregate,
  DatasetFilterOperator,
  ReportDatasetFieldRead,
  ReportMetricConfig,
  ReportQueryConfig,
} from '@/types/customReports';

interface FilterDraft {
  field: string;
  op: DatasetFilterOperator;
  value: string;
}

const store = useCustomReportStore();
const authStore = useAuthStore();

const reportName = ref('');
const reportDescription = ref('');
const selectedDatasetKey = ref('');
const selectedDimensions = ref<string[]>([]);
const metricField = ref('');
const metricAggregate = ref<DatasetAggregate>('sum');
const chartType = ref<CustomReportChartType>('table');
const shareScope = ref<CustomReportShareScope>('private');
const limit = ref(100);
const scheduleFrequency = ref<CustomReportScheduleFrequency | ''>('');
const scheduleTime = ref('09:00');
const scheduleDayOfWeek = ref(1);
const scheduleDayOfMonth = ref(1);
const scheduleTimezone = ref(authStore.user?.timezone ?? 'Asia/Hong_Kong');
const filters = reactive<FilterDraft[]>([]);

const reportRows = computed(() => store.reports as unknown as Record<string, unknown>[]);
const datasetRows = computed(() => store.datasets as unknown as Record<string, unknown>[]);
const selectedDataset = computed(
  () => store.datasets.find((dataset) => dataset.key === selectedDatasetKey.value) ?? null,
);
const fields = computed(() => selectedDataset.value?.fields ?? []);
const metricFields = computed(() => fields.value.filter((field) => field.aggregates.length > 0));
const selectedMetricField = computed(() =>
  metricFields.value.find((field) => field.key === metricField.value),
);
const hasInvalidFilter = computed(() =>
  filters.some((filter) => {
    if (!filter.field || !filter.op) {
      return true;
    }
    return !['is_null', 'is_not_null'].includes(filter.op) && !filter.value.trim();
  }),
);
const hasInvalidSchedule = computed(
  () =>
    Boolean(scheduleFrequency.value) &&
    (!scheduleTime.value.trim() || !scheduleTimezone.value.trim()),
);
const canSave = computed(
  () =>
    Boolean(reportName.value.trim() && selectedDataset.value) &&
    !hasInvalidFilter.value &&
    !hasInvalidSchedule.value,
);
const previewRows = computed(() => store.preview?.rows ?? []);
const previewColumns = computed(() => store.preview?.columns ?? []);

const datasetColumns = [
  { key: 'label', label: '数据集', minWidth: 160 },
  { key: 'description', label: '说明', minWidth: 260 },
];
const reportColumns = [
  { key: 'name', label: '报表', minWidth: 180 },
  { key: 'dataset', label: '数据集', width: 160 },
  { key: 'share_scope', label: '共享', width: 120 },
  { key: 'next_run_at', label: '下次生成', width: 180 },
  { key: 'actions', label: '操作', width: 210 },
];

onMounted(async () => {
  await store.fetchMetadata();
  selectedDatasetKey.value = store.datasets[0]?.key ?? '';
});

watch(selectedDataset, (dataset) => {
  selectedDimensions.value = dataset?.fields[0] ? [dataset.fields[0].key] : [];
  metricField.value = '';
  metricAggregate.value = 'sum';
  filters.splice(0, filters.length);
});

function buildQueryConfig(): ReportQueryConfig {
  const metrics: ReportMetricConfig[] =
    metricField.value && metricAggregate.value
      ? [
          {
            aggregate: metricAggregate.value,
            alias: `${metricAggregate.value}_${metricField.value}`,
            field: metricField.value,
          },
        ]
      : [];
  return {
    dataset: selectedDatasetKey.value,
    dimensions: selectedDimensions.value,
    filters: filters.map((filter) => ({
      field: filter.field,
      op: filter.op,
      value: normalizeFilterValue(filter),
    })),
    limit: limit.value,
    metrics,
    sort: [],
  };
}

function normalizeFilterValue(filter: FilterDraft): unknown {
  if (['is_null', 'is_not_null'].includes(filter.op)) {
    return null;
  }
  const field = fields.value.find((item) => item.key === filter.field);
  return field?.type === 'number' ? Number(filter.value) : filter.value;
}

async function runPreview(): Promise<void> {
  await store.previewReport(buildQueryConfig());
}

async function previewSavedReport(report: CustomReportDefinitionRead): Promise<void> {
  chartType.value = report.chart_type;
  await store.previewReport(report.query_config);
}

async function saveReport(): Promise<void> {
  if (!canSave.value) {
    return;
  }
  await store.createReport({
    chart_type: chartType.value,
    description: reportDescription.value.trim() || null,
    name: reportName.value.trim(),
    query_config: buildQueryConfig(),
    ...buildSchedulePayload(),
    share_scope: shareScope.value,
  });
  ElMessage.success('报表已保存');
}

async function deleteReport(report: CustomReportDefinitionRead): Promise<void> {
  await store.deleteReport(report.id);
  ElMessage.success('报表已删除');
}

async function openReport(report: CustomReportDefinitionRead): Promise<void> {
  await applyReport(report, 'open');
  await previewSavedReport(report);
}

async function copyReport(report: CustomReportDefinitionRead): Promise<void> {
  await applyReport(report, 'copy');
  ElMessage.success('报表已复制到设计器');
}

async function applyReport(
  report: CustomReportDefinitionRead,
  mode: 'copy' | 'open',
): Promise<void> {
  selectedDatasetKey.value = report.query_config.dataset;
  await nextTick();
  const primaryMetric = report.query_config.metrics[0];

  reportName.value = mode === 'copy' ? `${report.name} 副本` : report.name;
  reportDescription.value = report.description ?? '';
  selectedDimensions.value = [...report.query_config.dimensions];
  metricField.value = primaryMetric?.field ?? '';
  metricAggregate.value = primaryMetric?.aggregate ?? 'sum';
  chartType.value = report.chart_type;
  shareScope.value = mode === 'copy' ? 'private' : report.share_scope;
  limit.value = report.query_config.limit;
  scheduleFrequency.value = report.schedule_frequency ?? '';
  scheduleTime.value = normalizeScheduleTime(report.schedule_time);
  scheduleDayOfWeek.value = report.schedule_day_of_week ?? 1;
  scheduleDayOfMonth.value = report.schedule_day_of_month ?? 1;
  scheduleTimezone.value = report.schedule_timezone ?? authStore.user?.timezone ?? 'Asia/Hong_Kong';
  filters.splice(
    0,
    filters.length,
    ...report.query_config.filters.map((filter) => ({
      field: filter.field,
      op: filter.op,
      value: filter.value == null ? '' : String(filter.value),
    })),
  );
}

function buildSchedulePayload(): {
  schedule_day_of_month: number | null;
  schedule_day_of_week: number | null;
  schedule_frequency: CustomReportScheduleFrequency | null;
  schedule_time: string | null;
  schedule_timezone: string | null;
} {
  if (!scheduleFrequency.value) {
    return {
      schedule_day_of_month: null,
      schedule_day_of_week: null,
      schedule_frequency: null,
      schedule_time: null,
      schedule_timezone: null,
    };
  }
  return {
    schedule_day_of_month: scheduleFrequency.value === 'monthly' ? scheduleDayOfMonth.value : null,
    schedule_day_of_week: scheduleFrequency.value === 'weekly' ? scheduleDayOfWeek.value : null,
    schedule_frequency: scheduleFrequency.value,
    schedule_time: scheduleTime.value,
    schedule_timezone: scheduleTimezone.value,
  };
}

function normalizeScheduleTime(value: string | null | undefined): string {
  return value ? value.slice(0, 5) : '09:00';
}

function addFilter(): void {
  const field = fields.value[0];
  if (!field) {
    return;
  }
  filters.push({ field: field.key, op: field.filter_ops[0] ?? 'eq', value: '' });
}

function removeFilter(index: number): void {
  filters.splice(index, 1);
}

function datasetLabel(key: string): string {
  return store.datasets.find((dataset) => dataset.key === key)?.label ?? key;
}

function rowRecord(row: unknown): Record<string, unknown> {
  return row && typeof row === 'object' ? (row as Record<string, unknown>) : {};
}

function rowText(row: unknown, key: string): string {
  const value = rowRecord(row)[key];
  return typeof value === 'string' ? value : '';
}

function datasetFields(row: unknown): ReportDatasetFieldRead[] {
  const value = rowRecord(row).fields;
  return Array.isArray(value) ? (value as ReportDatasetFieldRead[]) : [];
}

function asReport(row: unknown): CustomReportDefinitionRead {
  return row as unknown as CustomReportDefinitionRead;
}

function canDelete(report: CustomReportDefinitionRead): boolean {
  return authStore.user?.role === 'admin' || authStore.user?.id === report.owner_id;
}

function filterOps(fieldKey: string): DatasetFilterOperator[] {
  return fields.value.find((field) => field.key === fieldKey)?.filter_ops ?? [];
}

function aggregateOptions(field: ReportDatasetFieldRead | null | undefined): DatasetAggregate[] {
  return field?.aggregates ?? [];
}
</script>

<template>
  <section class="report-builder">
    <div class="report-builder__header">
      <div>
        <h2>项目查询</h2>
        <p>按项目数据集、字段和筛选条件直接查询结果。</p>
      </div>
      <el-button :icon="Refresh" :loading="store.loading" @click="store.fetchMetadata">
        刷新
      </el-button>
    </div>

    <div class="report-builder__mobile-note">
      移动端仅支持查看查询结果，复杂条件请在桌面端完成。
    </div>

    <div class="report-builder__workspace">
      <section class="report-builder__panel report-builder__panel--builder">
        <h3>查询条件</h3>
        <div class="report-builder__form-grid">
          <label>
            <span>报表名称</span>
            <el-input v-model="reportName" data-test="report-name" />
          </label>
          <label>
            <span>数据集</span>
            <el-select v-model="selectedDatasetKey" data-test="dataset-select">
              <el-option
                v-for="dataset in store.datasets"
                :key="dataset.key"
                :label="dataset.label"
                :value="dataset.key"
              />
            </el-select>
          </label>
          <label>
            <span>图表</span>
            <el-select v-model="chartType">
              <el-option label="表格" value="table" />
              <el-option label="柱状" value="bar" />
              <el-option label="折线" value="line" />
            </el-select>
          </label>
          <label>
            <span>共享</span>
            <el-select v-model="shareScope">
              <el-option label="私有" value="private" />
              <el-option label="部门" value="department" />
              <el-option label="全局" value="global" />
            </el-select>
          </label>
        </div>

        <label class="report-builder__description">
          <span>说明</span>
          <el-input v-model="reportDescription" />
        </label>

        <section class="report-builder__field-section">
          <h4>定时生成</h4>
          <div class="report-builder__schedule-grid">
            <label>
              <span>频率</span>
              <el-select v-model="scheduleFrequency" data-test="schedule-frequency">
                <el-option label="不启用" value="" />
                <el-option label="每日" value="daily" />
                <el-option label="每周" value="weekly" />
                <el-option label="每月" value="monthly" />
              </el-select>
            </label>
            <label v-if="scheduleFrequency">
              <span>时间</span>
              <el-input v-model="scheduleTime" data-test="schedule-time" />
            </label>
            <label v-if="scheduleFrequency === 'weekly'">
              <span>星期</span>
              <el-input-number
                v-model="scheduleDayOfWeek"
                data-test="schedule-day-of-week"
                :max="7"
                :min="1"
              />
            </label>
            <label v-if="scheduleFrequency === 'monthly'">
              <span>日期</span>
              <el-input-number
                v-model="scheduleDayOfMonth"
                data-test="schedule-day-of-month"
                :max="31"
                :min="1"
              />
            </label>
            <label v-if="scheduleFrequency">
              <span>时区</span>
              <el-input v-model="scheduleTimezone" data-test="schedule-timezone" />
            </label>
          </div>
        </section>

        <section class="report-builder__field-section">
          <h4>维度</h4>
          <el-checkbox-group v-model="selectedDimensions">
            <el-checkbox v-for="field in fields" :key="field.key" :label="field.key">
              {{ field.label }}
            </el-checkbox>
          </el-checkbox-group>
        </section>

        <section class="report-builder__field-section">
          <h4>指标</h4>
          <div class="report-builder__metric-row">
            <el-select v-model="metricField">
              <el-option label="不使用指标" value="" />
              <el-option
                v-for="field in metricFields"
                :key="field.key"
                :label="field.label"
                :value="field.key"
              />
            </el-select>
            <el-select v-model="metricAggregate" :disabled="!metricField">
              <el-option
                v-for="aggregate in aggregateOptions(selectedMetricField)"
                :key="aggregate"
                :label="aggregate"
                :value="aggregate"
              />
            </el-select>
            <el-input-number v-model="limit" :max="1000" :min="1" />
          </div>
        </section>

        <section class="report-builder__field-section">
          <div class="report-builder__section-title">
            <h4>筛选</h4>
            <el-button data-test="add-filter" size="small" @click="addFilter">添加</el-button>
          </div>
          <div
            v-for="(filter, index) in filters"
            :key="`${filter.field}-${index}`"
            class="report-builder__filter-row"
          >
            <el-select v-model="filter.field">
              <el-option
                v-for="field in fields"
                :key="field.key"
                :label="field.label"
                :value="field.key"
              />
            </el-select>
            <el-select v-model="filter.op">
              <el-option v-for="op in filterOps(filter.field)" :key="op" :label="op" :value="op" />
            </el-select>
            <el-input v-model="filter.value" />
            <el-button :icon="Delete" circle @click="removeFilter(index)" />
          </div>
        </section>

        <div class="report-builder__actions">
          <el-button
            data-test="run-project-query"
            :icon="View"
            :loading="store.previewing"
            @click="runPreview"
          >
            查询
          </el-button>
          <el-button
            data-test="save-report"
            :disabled="!canSave"
            :icon="Check"
            :loading="store.submitting"
            type="primary"
            @click="saveReport"
          >
            保存
          </el-button>
        </div>
      </section>

      <section class="report-builder__panel report-builder__panel--preview">
        <h3>预览</h3>
        <ReportChartPreview :chart-type="chartType" :columns="previewColumns" :rows="previewRows" />
      </section>
    </div>

    <section class="report-builder__panel report-builder__dataset-panel">
      <h3>数据集字段</h3>
      <DataTable
        :columns="datasetColumns"
        :loading="store.loading"
        :page="1"
        :page-size="store.datasets.length || 1"
        :rows="datasetRows"
        :total="store.datasets.length"
      >
        <template #description="{ row }">
          <span>{{ rowText(row, 'description') }}</span>
          <el-tag
            v-for="field in datasetFields(row)"
            :key="field.key"
            class="report-builder__field-tag"
          >
            {{ field.label }}
          </el-tag>
        </template>
      </DataTable>
    </section>

    <section class="report-builder__panel">
      <h3>查询方案</h3>
      <DataTable
        :columns="reportColumns"
        :loading="store.loading"
        :page="1"
        :page-size="store.reports.length || 1"
        :rows="reportRows"
        :total="store.reports.length"
      >
        <template #dataset="{ value }">
          {{ datasetLabel(String(value)) }}
        </template>
        <template #actions="{ row }">
          <el-button
            data-test="open-report"
            :icon="EditPen"
            aria-label="打开"
            size="small"
            title="打开"
            @click="openReport(asReport(row))"
          />
          <el-button
            data-test="copy-report"
            :icon="CopyDocument"
            aria-label="复制"
            size="small"
            title="复制"
            @click="copyReport(asReport(row))"
          />
          <el-button
            data-test="preview-saved-report"
            :icon="View"
            aria-label="预览"
            size="small"
            title="预览"
            @click="previewSavedReport(asReport(row))"
          />
          <el-button
            v-if="canDelete(asReport(row))"
            data-test="delete-report"
            :icon="Delete"
            aria-label="删除"
            size="small"
            title="删除"
            @click="deleteReport(asReport(row))"
          />
        </template>
      </DataTable>
    </section>
  </section>
</template>

<style scoped>
.report-builder {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.report-builder__header,
.report-builder__section-title,
.report-builder__actions,
.report-builder__metric-row,
.report-builder__filter-row {
  display: flex;
  gap: 12px;
}

.report-builder__header,
.report-builder__section-title,
.report-builder__actions {
  align-items: center;
  justify-content: space-between;
}

.report-builder__header h2,
.report-builder__panel h3,
.report-builder__field-section h4 {
  margin: 0;
}

.report-builder__header p {
  margin: 6px 0 0;
  color: #667085;
}

.report-builder__mobile-note {
  display: none;
  border: 1px solid #f3d19e;
  border-radius: 8px;
  background: #fdf6ec;
  color: #b26a00;
  padding: 10px 12px;
}

.report-builder__workspace {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
}

.report-builder__panel {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 18px;
}

.report-builder__panel--builder,
.report-builder__panel--preview {
  min-height: 360px;
}

.report-builder__form-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 16px;
}

.report-builder__schedule-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  margin-top: 10px;
}

.report-builder__description,
.report-builder__form-grid label,
.report-builder__schedule-grid label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.report-builder__description {
  margin-top: 14px;
}

.report-builder__field-section {
  margin-top: 18px;
}

.report-builder__metric-row,
.report-builder__filter-row {
  align-items: center;
  flex-wrap: wrap;
  margin-top: 10px;
}

.report-builder__field-tag {
  margin-left: 6px;
  margin-top: 4px;
}

.report-builder__actions {
  justify-content: flex-end;
  margin-top: 18px;
}

@media (width <= 1100px) {
  .report-builder__workspace,
  .report-builder__form-grid,
  .report-builder__schedule-grid {
    grid-template-columns: 1fr;
  }
}

@media (width <= 760px) {
  .report-builder__mobile-note {
    display: block;
  }

  .report-builder__panel--builder,
  .report-builder__dataset-panel {
    display: none;
  }
}
</style>
