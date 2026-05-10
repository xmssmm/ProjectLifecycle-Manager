<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { usePaymentStore } from '@/stores/usePaymentStore';
import {
  PAYMENT_TYPE_LABELS,
  PAYMENT_TYPE_OPTIONS,
  type PaymentCreatePayload,
  type PaymentListQuery,
  type PaymentType,
} from '@/types/payments';

const props = defineProps<{
  subProjectId: string;
}>();

const paymentStore = usePaymentStore();
const createDialogVisible = ref(false);
const errorMessage = ref('');
const selectedFiles = ref<File[]>([]);
const submitting = ref(false);
const filterState = reactive({
  paymentType: '',
});
const createForm = reactive({
  amount: '',
  paymentDate: '',
  remark: '',
});

const paymentRows = computed(() => paymentStore.payments);

onMounted(loadPayments);

watch(
  () => props.subProjectId,
  async () => {
    resetFilter();
    await loadPayments();
  },
);

async function loadPayments(query: PaymentListQuery = { page: 1, pageSize: 20 }): Promise<void> {
  await paymentStore.fetchPayments(props.subProjectId, query);
}

async function searchPayments(): Promise<void> {
  await loadPayments(buildQuery());
}

async function submitPayment(): Promise<void> {
  const payload = buildCreatePayload();
  if (!payload) {
    return;
  }

  submitting.value = true;
  try {
    await paymentStore.createPayment(payload);
    resetCreateForm();
    createDialogVisible.value = false;
    ElMessage.success('付款已新增');
    await loadPayments(buildQuery());
  } finally {
    submitting.value = false;
  }
}

function buildQuery(): PaymentListQuery {
  const query: PaymentListQuery = { page: 1, pageSize: 20 };
  if (filterState.paymentType) {
    query.paymentType = filterState.paymentType as PaymentType;
  }
  return query;
}

function buildCreatePayload(): PaymentCreatePayload | null {
  errorMessage.value = '';
  if (!createForm.amount.trim() || !createForm.paymentDate) {
    errorMessage.value = '金额和日期必填';
    return null;
  }
  if (selectedFiles.value.length === 0) {
    errorMessage.value = '付款凭证必传';
    return null;
  }
  return {
    amount: createForm.amount.trim(),
    files: selectedFiles.value,
    paymentDate: createForm.paymentDate,
    remark: createForm.remark.trim() || null,
    subProjectId: props.subProjectId,
  };
}

function handleFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectedFiles.value = Array.from(input.files ?? []);
}

function resetCreateForm(): void {
  createForm.amount = '';
  createForm.paymentDate = '';
  createForm.remark = '';
  selectedFiles.value = [];
  errorMessage.value = '';
}

function resetFilter(): void {
  filterState.paymentType = '';
}

function formatMoney(value: string): string {
  const amount = Number(value);
  return Number.isFinite(amount)
    ? amount.toLocaleString('zh-CN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
    : value;
}

function formatDate(value: string): string {
  return value ? value.slice(0, 10) : '-';
}

function paymentTypeLabel(type: PaymentType): string {
  return PAYMENT_TYPE_LABELS[type];
}

function paymentTypeTag(type: PaymentType): 'danger' | 'success' {
  return type === 'reversal' ? 'danger' : 'success';
}
</script>

<template>
  <section class="admin-page project-page payment-page">
    <div class="admin-page__header">
      <div>
        <h2>付款记录</h2>
        <p>{{ subProjectId }}</p>
      </div>
      <el-button data-test="open-create-payment" type="primary" @click="createDialogVisible = true">
        新增付款
      </el-button>
    </div>

    <section class="payment-filter-band">
      <label class="payment-field">
        <span>类型</span>
        <el-select v-model="filterState.paymentType" data-test="payment-type-filter">
          <el-option
            v-for="option in PAYMENT_TYPE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </label>
      <el-button
        data-test="search-payments"
        :loading="paymentStore.loading"
        @click="searchPayments"
      >
        查询
      </el-button>
    </section>

    <section class="admin-page__table payment-table-band">
      <table class="payment-table">
        <thead>
          <tr>
            <th>付款编号</th>
            <th>类型</th>
            <th>金额</th>
            <th>付款日期</th>
            <th>红冲来源</th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="payment in paymentRows" :key="payment.id">
            <td>{{ payment.payment_no }}</td>
            <td>
              <el-tag :type="paymentTypeTag(payment.payment_type)">
                {{ paymentTypeLabel(payment.payment_type) }}
              </el-tag>
            </td>
            <td
              class="payment-table__amount"
              :class="{ 'is-negative': Number(payment.amount) < 0 }"
            >
              {{ formatMoney(payment.amount) }}
            </td>
            <td>{{ formatDate(payment.payment_date) }}</td>
            <td>{{ payment.reverses_payment_id ?? '-' }}</td>
            <td>{{ payment.remark || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <el-empty
        v-if="!paymentStore.loading && paymentRows.length === 0"
        description="暂无付款记录"
      />
    </section>

    <el-dialog v-model="createDialogVisible" title="新增付款" width="560px">
      <el-form label-position="top" class="payment-form" @submit.prevent>
        <el-form-item label="金额">
          <el-input v-model="createForm.amount" data-test="payment-amount" />
        </el-form-item>
        <el-form-item label="付款日期">
          <el-input v-model="createForm.paymentDate" data-test="payment-date" type="date" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" data-test="payment-remark" />
        </el-form-item>
        <el-form-item label="付款凭证">
          <!-- prettier-ignore -->
          <input data-test="payment-file" type="file" multiple @change="handleFileChange">
          <span class="payment-form__file-name">
            {{ selectedFiles.map((file) => file.name).join(', ') }}
          </span>
        </el-form-item>
        <el-alert v-if="errorMessage" :closable="false" :title="errorMessage" type="error" />
      </el-form>
      <template #footer>
        <div class="project-form-actions">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button
            data-test="submit-payment"
            :loading="submitting"
            type="primary"
            @click="submitPayment"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
