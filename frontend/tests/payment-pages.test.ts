import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createPayment, listPayments, reversePayment } from '@/api/payments';
import { deleteDocument } from '@/api/documents';
import { useAuthStore } from '@/stores/useAuthStore';
import type { PaymentRead } from '@/types/payments';
import PaymentList from '@/views/payment/PaymentList.vue';

vi.mock('@/api/payments', () => ({
  createPayment: vi.fn(),
  getPayment: vi.fn(),
  listPayments: vi.fn(),
  reversePayment: vi.fn(),
}));

vi.mock('@/api/documents', () => ({
  deleteDocument: vi.fn(),
  downloadDocument: vi.fn(),
}));

describe('PaymentList', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    const authStore = useAuthStore();
    authStore.setAccessToken('finance-token');
    authStore.setUser({
      deptId: 'dept-a',
      email: null,
      id: 'finance-1',
      role: 'finance_manager',
      status: 'active',
      username: 'finance',
    });
    vi.mocked(listPayments).mockResolvedValue({
      items: [samplePayment, reversalPayment],
      page: 1,
      page_size: 20,
      total: 2,
    });
    vi.mocked(createPayment).mockResolvedValue(newPayment);
    vi.mocked(reversePayment).mockResolvedValue(reversalPayment);
    vi.mocked(deleteDocument).mockResolvedValue({
      acceptance_step_id: null,
      created_at: '2026-05-10T00:00:00Z',
      display_name: 'voucher.pdf',
      doc_no: 'DOC-1',
      doc_type: 'payment_voucher',
      file_name: 'voucher.pdf',
      file_size: 1024,
      id: 'doc-1',
      is_deleted: true,
      is_latest: false,
      phase_id: 'phase-5',
      scan_result: null,
      scan_status: 'clean',
      scanned_at: null,
      sub_project_id: 'sub-1',
      updated_at: '2026-05-10T00:00:00Z',
      uploader_id: 'finance-1',
      version: 1,
    });
  });

  it('lists payments, filters by type, and creates a payment with voucher', async () => {
    const wrapper = mount(PaymentList, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    expect(listPayments).toHaveBeenCalledWith('sub-1', { page: 1, pageSize: 20 });
    expect(wrapper.text()).toContain('Z-2026-0001-ZX-001-PAY-001');
    expect(wrapper.text()).toContain('voucher.pdf');
    expect(wrapper.text()).toContain('reversal');

    await wrapper.find('[data-test="payment-type-filter"]').setValue('reversal');
    await wrapper.find('[data-test="search-payments"]').trigger('click');
    await flushPromises();

    expect(listPayments).toHaveBeenLastCalledWith('sub-1', {
      page: 1,
      pageSize: 20,
      paymentType: 'reversal',
    });

    await wrapper.find('[data-test="open-create-payment"]').trigger('click');
    await wrapper.find('[data-test="payment-amount"]').setValue('50.00');
    await wrapper.find('[data-test="payment-date"]').setValue('2026-05-12');
    await wrapper.find('[data-test="payment-remark"]').setValue('second payment');
    await setFile(wrapper.find('[data-test="payment-file"]').element as HTMLInputElement);
    await wrapper.find('[data-test="submit-payment"]').trigger('click');
    await flushPromises();

    expect(createPayment).toHaveBeenCalledWith({
      amount: '50.00',
      files: [expect.objectContaining({ name: 'voucher.pdf' })],
      paymentDate: '2026-05-12',
      remark: 'second payment',
      subProjectId: 'sub-1',
    });

    expect(wrapper.find('[data-test="mobile-read-only-payment"]').text()).toContain(
      '移动端仅支持查看付款记录',
    );
    expect(wrapper.find('[data-test="open-create-payment"]').classes()).toContain(
      'desktop-only-action',
    );

    await wrapper.find('[data-test="delete-payment-voucher"]').trigger('click');
    await flushPromises();

    expect(deleteDocument).toHaveBeenCalledWith('doc-1');
  });

  it('confirms over-budget create and reverses normal payments with a reason', async () => {
    vi.mocked(createPayment)
      .mockRejectedValueOnce({
        response: {
          data: {
            code: 3001,
            data: { budget: '100.00', over_amount: '20.50' },
            message: 'over budget',
          },
        },
      })
      .mockResolvedValueOnce(newPayment);
    const wrapper = mount(PaymentList, {
      global: { stubs },
      props: { subProjectId: 'sub-1' },
    });
    await flushPromises();

    await wrapper.find('[data-test="open-create-payment"]').trigger('click');
    await wrapper.find('[data-test="payment-amount"]').setValue('120.50');
    await wrapper.find('[data-test="payment-date"]').setValue('2026-05-12');
    await setFile(wrapper.find('[data-test="payment-file"]').element as HTMLInputElement);
    await wrapper.find('[data-test="submit-payment"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-test="over-budget-reason"]').exists()).toBe(true);

    await wrapper.find('[data-test="over-budget-reason"]').setValue('approved');
    await wrapper.find('[data-test="confirm-over-budget"]').trigger('click');
    await flushPromises();

    expect(createPayment).toHaveBeenLastCalledWith({
      amount: '120.50',
      confirmOverBudget: true,
      files: [expect.objectContaining({ name: 'voucher.pdf' })],
      overBudgetReason: 'approved',
      paymentDate: '2026-05-12',
      remark: null,
      subProjectId: 'sub-1',
    });

    await wrapper.find('[data-test="reverse-payment"]').trigger('click');
    await wrapper.find('[data-test="reversal-reason"]').setValue('wrong amount');
    await wrapper.find('[data-test="submit-reversal"]').trigger('click');
    await flushPromises();

    expect(reversePayment).toHaveBeenCalledWith({
      remark: 'wrong amount',
      reversesPaymentId: 'pay-1',
      subProjectId: 'sub-1',
    });
  });
});

async function setFile(input: HTMLInputElement): Promise<void> {
  const file = new File(['%PDF-1.7'], 'voucher.pdf', { type: 'application/pdf' });
  Object.defineProperty(input, 'files', {
    configurable: true,
    value: [file],
  });
  input.dispatchEvent(new Event('change'));
  await flushPromises();
}

const samplePayment: PaymentRead = {
  amount: '120.50',
  created_at: '2026-05-10T00:00:00Z',
  id: 'pay-1',
  operator_id: 'finance-1',
  payment_date: '2026-05-10',
  payment_no: 'Z-2026-0001-ZX-001-PAY-001',
  payment_type: 'normal',
  remark: 'first payment',
  reverses_payment_id: null,
  sub_project_id: 'sub-1',
  updated_at: '2026-05-10T00:00:00Z',
  vouchers: [
    {
      created_at: '2026-05-10T00:00:00Z',
      document: {
        created_at: '2026-05-10T00:00:00Z',
        display_name: 'voucher.pdf',
        doc_type: 'payment_voucher',
        file_name: 'voucher.pdf',
        file_size: 1024,
        id: 'doc-1',
        is_deleted: false,
        updated_at: '2026-05-10T00:00:00Z',
        uploader_id: 'finance-1',
        version: 1,
      },
      document_id: 'doc-1',
      id: 'voucher-1',
      payment_id: 'pay-1',
      updated_at: '2026-05-10T00:00:00Z',
    },
  ],
};

const reversalPayment: PaymentRead = {
  ...samplePayment,
  amount: '-120.50',
  id: 'pay-2',
  payment_no: 'Z-2026-0001-ZX-001-PAY-002',
  payment_type: 'reversal',
  reverses_payment_id: 'pay-1',
};

const newPayment: PaymentRead = {
  ...samplePayment,
  amount: '50.00',
  id: 'pay-3',
  payment_date: '2026-05-12',
  payment_no: 'Z-2026-0001-ZX-001-PAY-003',
  remark: 'second payment',
};

const stubs = {
  ElAlert: { props: ['title'], template: '<section>{{ title }}</section>' },
  ElButton: {
    emits: ['click'],
    props: ['disabled', 'loading', 'type'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  ElDialog: {
    props: ['modelValue'],
    template: '<section v-if="modelValue"><slot /><slot name="footer" /></section>',
  },
  ElEmpty: { props: ['description'], template: '<section>{{ description }}</section>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
  ElInput: {
    props: ['modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElOption: {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  ElSelect: {
    props: ['modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  ElTag: { props: ['type'], template: '<span><slot /></span>' },
};
