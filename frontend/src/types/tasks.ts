export type TaskStatus = 'not_started' | 'in_progress' | 'overdue' | 'completed';

export interface TaskExecutorRead {
  actual_end_date: string | null;
  created_at: string;
  id: string;
  plan_end_date: string;
  status: TaskStatus;
  task_id: string;
  updated_at: string;
  user_id: string;
}

export interface TaskRead {
  created_at: string;
  executors: TaskExecutorRead[];
  id: string;
  name: string;
  phase_id: string;
  plan_end_date: string;
  status: TaskStatus;
  sub_project_id: string;
  task_no: string;
  updated_at: string;
}

export interface TaskListRead {
  items: TaskRead[];
  total: number;
}

export interface TaskListQuery {
  assignee?: 'me';
  status?: TaskStatus;
  subProjectId?: string;
}

export interface TaskExecutorAssignPayload {
  plan_end_date: string;
  user_id: string;
}

export interface TaskCreatePayload {
  executors: TaskExecutorAssignPayload[];
  name: string;
  phase_id: string;
  plan_end_date: string;
  sub_project_id: string;
}

export type TaskUpdatePayload = Partial<TaskCreatePayload>;

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  completed: '已完成',
  in_progress: '进行中',
  not_started: '未开始',
  overdue: '已逾期',
};

export const TASK_STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: TASK_STATUS_LABELS.not_started, value: 'not_started' },
  { label: TASK_STATUS_LABELS.in_progress, value: 'in_progress' },
  { label: TASK_STATUS_LABELS.overdue, value: 'overdue' },
  { label: TASK_STATUS_LABELS.completed, value: 'completed' },
] as const;
