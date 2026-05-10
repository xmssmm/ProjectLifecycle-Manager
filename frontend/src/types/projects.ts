export type ProjectStatus =
  | 'pending_review'
  | 'reviewing'
  | 'rejected'
  | 'not_started'
  | 'in_progress'
  | 'completed'
  | 'closed'
  | 'terminated';

export interface MainProjectRead {
  created_at: string;
  creator_id: string | null;
  dept_id: string;
  expected_finish_date: string | null;
  id: string;
  name: string;
  project_no: string;
  remark: string | null;
  spent_amount: string;
  status: ProjectStatus;
  total_budget: string;
  updated_at: string;
}

export interface MainProjectListRead {
  items: MainProjectRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface MainProjectListQuery {
  page: number;
  pageSize: number;
}

export interface MainProjectCreatePayload {
  dept_id: string;
  expected_finish_date: string;
  name: string;
  remark: string | null;
  total_budget: string;
}

export type MainProjectUpdatePayload = Partial<MainProjectCreatePayload>;

export type ProjectReviewDecision = 'approve' | 'reject';

export interface MainProjectReviewPayload {
  decision: ProjectReviewDecision;
  review_comment: string | null;
  updates: MainProjectUpdatePayload | null;
}

export interface SubProjectRead {
  actual_end_date: string | null;
  budget: string;
  created_at: string;
  creator_id: string | null;
  dept_id: string;
  id: string;
  main_project_id: string;
  manager_id: string;
  name: string;
  plan_end_date: string | null;
  project_no: string;
  remark: string | null;
  spent_amount: string;
  status: ProjectStatus;
  updated_at: string;
}

export interface SubProjectListRead {
  items: SubProjectRead[];
  page: number;
  page_size: number;
  total: number;
}

export interface SubProjectListQuery {
  page: number;
  pageSize: number;
}

export interface SubProjectCreatePayload {
  budget: string;
  dept_id: string;
  main_project_id: string;
  name: string;
  plan_end_date: string | null;
  remark: string | null;
}

export type SubProjectUpdatePayload = Partial<Omit<SubProjectCreatePayload, 'main_project_id'>>;

export interface SubProjectReviewPayload {
  confirm_over_budget: boolean;
  decision: ProjectReviewDecision;
  over_budget_reason: string | null;
  review_comment: string | null;
  updates: SubProjectUpdatePayload | null;
}

export interface SubProjectTerminatePayload {
  reason: string;
}

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  pending_review: '待审核',
  reviewing: '审核中',
  rejected: '已退回',
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  closed: '已结项',
  terminated: '已中止',
};

export const MAIN_PROJECT_STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: PROJECT_STATUS_LABELS.pending_review, value: 'pending_review' },
  { label: PROJECT_STATUS_LABELS.reviewing, value: 'reviewing' },
  { label: PROJECT_STATUS_LABELS.rejected, value: 'rejected' },
  { label: PROJECT_STATUS_LABELS.not_started, value: 'not_started' },
  { label: PROJECT_STATUS_LABELS.in_progress, value: 'in_progress' },
  { label: PROJECT_STATUS_LABELS.completed, value: 'completed' },
  { label: PROJECT_STATUS_LABELS.closed, value: 'closed' },
] as const;

export const SUB_PROJECT_STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: PROJECT_STATUS_LABELS.pending_review, value: 'pending_review' },
  { label: PROJECT_STATUS_LABELS.reviewing, value: 'reviewing' },
  { label: PROJECT_STATUS_LABELS.rejected, value: 'rejected' },
  { label: PROJECT_STATUS_LABELS.not_started, value: 'not_started' },
  { label: PROJECT_STATUS_LABELS.in_progress, value: 'in_progress' },
  { label: PROJECT_STATUS_LABELS.completed, value: 'completed' },
  { label: PROJECT_STATUS_LABELS.closed, value: 'closed' },
  { label: PROJECT_STATUS_LABELS.terminated, value: 'terminated' },
] as const;

export const MAIN_PROJECT_TIMELINE: ProjectStatus[] = [
  'pending_review',
  'reviewing',
  'rejected',
  'not_started',
  'in_progress',
  'completed',
  'closed',
];
