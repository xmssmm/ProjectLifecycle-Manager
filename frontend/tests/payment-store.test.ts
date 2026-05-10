import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createPayment, getPayment, listPayments, reversePayment } from '@/api/payments';
import { usePaymentStore } from '@/stores/usePaymentStore';
import type { PaymentRead } from '@/types/payments';

vi.mock('@/api/payments', () => ({
  createPayment: vi.fn(),
  getPayment: vi.fn(),
  listPayments: vi.fn(),
  reversePayment: vi.fn(),
}));

describe('payment store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('loads payments, keeps detail, and inserts newly created payment', async () => {
    vi.mocked(listPayments).mockResolvedValue({
      items: [samplePayment],
      page: 1,
      page_size: 20,
      total: 1,
    });
    vi.mocked(getPayment).mockResolvedValue(samplePayment);
    vi.mocked(createPayment).mockResolvedValue(newPayment);
    vi.mocked(reversePayment).mockResolvedValue(reversalPayment);
    const store = usePaymentStore();

    await store.fetchPayments('sub-1', { page: 1, pageSize: 20, paymentType: 'normal' });
    await store.fetchPaymentDetail('sub-1', 'pay-1');
    await store.createPayment({
      amount: '50.00',
      files: [new File(['%PDF-1.7'], 'voucher.pdf', { type: 'application/pdf' })],
      paymentDate: '2026-05-12',
      remark: 'second payment',
      subProjectId: 'sub-1',
    });
    await store.reversePayment({
      remark: 'wrong amount',
      reversesPaymentId: 'pay-1',
      subProjectId: 'sub-1',
    });

    expect(listPayments).toHaveBeenCalledWith('sub-1', {
      page: 1,
      pageSize: 20,
      paymentType: 'normal',
    });
    expect(getPayment).toHaveBeenCalledWith('sub-1', 'pay-1');
    expect(reversePayment).toHaveBeenCalledWith({
      remark: 'wrong amount',
      reversesPaymentId: 'pay-1',
      subProjectId: 'sub-1',
    });
    expect(store.currentPayment?.id).toBe('pay-3');
    expect(store.payments.map((payment) => payment.id)).toEqual(['pay-3', 'pay-2', 'pay-1']);
    expect(store.total).toBe(3);
  });
});

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
};

const newPayment: PaymentRead = {
  ...samplePayment,
  amount: '50.00',
  id: 'pay-2',
  payment_date: '2026-05-12',
  payment_no: 'Z-2026-0001-ZX-001-PAY-002',
  remark: 'second payment',
};

const reversalPayment: PaymentRead = {
  ...samplePayment,
  amount: '-120.50',
  id: 'pay-3',
  payment_no: 'Z-2026-0001-ZX-001-PAY-003',
  payment_type: 'reversal',
  remark: 'wrong amount',
  reverses_payment_id: 'pay-1',
};
