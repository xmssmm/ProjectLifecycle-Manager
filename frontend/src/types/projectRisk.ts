export type ProjectRiskLevel = 'critical' | 'high' | 'low' | 'medium';
export type ProjectRiskSummarySource = 'ai' | 'rules';

export interface ProjectRiskReason {
  code: string;
  message: string;
  score: number;
  severity: string;
}

export interface ProjectRiskSummary {
  recommendations: string[];
  source: ProjectRiskSummarySource;
  text: string;
}

export interface ProjectRiskRead {
  actions: string[];
  level: ProjectRiskLevel;
  project_id: string;
  reasons: ProjectRiskReason[];
  score: number;
  summary: ProjectRiskSummary;
}
