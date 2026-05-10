export type PaymentType = 'normal' | 'reversal';

export interface PaymentRead {
  amount: string;
  created_at: string;
  id: string;
  operator_id: string | null;
  payment_date: string;
  payment_no: string;
  payment_type: PaymentType;
  remark: string | null;
  reverses_payment_id: string | null;
  sub_project_id: string;
  updated_at: string;
}

export interface PaymentListRead {
  items: PaymentRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface PaymentListQuery {
  page?: number;
  pageSize?: number;
  paymentType?: PaymentType;
}

export interface PaymentCreatePayload {
  amount: string;
  confirmOverBudget?: boolean;
  files: File[];
  overBudgetReason?: string | null;
  paymentDate: string;
  remark?: string | null;
  subProjectId: string;
}

export interface PaymentReversePayload {
  remark: string;
  reversesPaymentId: string;
  subProjectId: string;
}

export const PAYMENT_TYPE_OPTIONS = [
  { label: '全部类型', value: '' },
  { label: '正常 normal', value: 'normal' },
  { label: '红冲 reversal', value: 'reversal' },
] as const;

export const PAYMENT_TYPE_LABELS: Record<PaymentType, string> = {
  normal: '正常 normal',
  reversal: '红冲 reversal',
};
