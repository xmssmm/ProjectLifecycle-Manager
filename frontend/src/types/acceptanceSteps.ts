export type AcceptanceStepStatus = 'not_started' | 'in_progress' | 'completed';

export interface AcceptanceStepRead {
  completed_at: string | null;
  created_at: string;
  description: string | null;
  id: string;
  phase_id: string;
  plan_date: string | null;
  responsible_id: string;
  status: AcceptanceStepStatus;
  step_name: string;
  step_no: number;
  updated_at: string;
}

export interface AcceptanceStepListRead {
  items: AcceptanceStepRead[];
  total: number;
}

export interface AcceptanceStepCreatePayload {
  description?: string | null;
  planDate?: string | null;
  responsibleId: string;
  stepName: string;
  stepNo: number;
}

export interface AcceptanceStepUpdatePayload {
  status: AcceptanceStepStatus;
}

export const ACCEPTANCE_STEP_STATUS_LABELS: Record<AcceptanceStepStatus, string> = {
  completed: '已完成',
  in_progress: '进行中',
  not_started: '未开始',
};
