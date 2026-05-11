from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.models.users import User
from app.services.ai_providers import (
    AiProviderDisabledError,
    AiProviderError,
    AiProviderService,
    AiSchemaValidationError,
)
from app.services.project_benchmarks import (
    BenchmarkMetric,
    BenchmarkProjectSnapshot,
    ProjectBenchmarkRepository,
    ProjectBenchmarkService,
)


@dataclass(frozen=True)
class RiskReason:
    code: str
    message: str
    score: int
    severity: str

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "score": self.score,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class RiskSummary:
    recommendations: list[str]
    source: str
    text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "recommendations": self.recommendations,
            "source": self.source,
            "text": self.text,
        }


@dataclass(frozen=True)
class ProjectRiskResult:
    actions: list[str]
    level: str
    project_id: UUID
    reasons: list[RiskReason]
    score: int
    summary: RiskSummary

    def to_dict(self) -> dict[str, object]:
        return {
            "actions": self.actions,
            "level": self.level,
            "project_id": str(self.project_id),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "score": self.score,
            "summary": self.summary.to_dict(),
        }


class ProjectRiskService:
    def __init__(
        self,
        *,
        ai_service: AiProviderService | None = None,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
        repository: ProjectBenchmarkRepository,
    ) -> None:
        self._ai_service = ai_service
        self._benchmark_service = ProjectBenchmarkService(
            now_provider=now_provider,
            repository=repository,
        )
        self._now_provider = now_provider
        self._repository = repository

    async def analyze_project(self, *, actor: User, project_id: UUID) -> ProjectRiskResult:
        benchmark = await self._benchmark_service.analyze_project(
            actor=actor,
            project_id=project_id,
        )
        project = await self._repository.get_project(project_id)
        if project is None:
            raise RuntimeError("Benchmark service returned a missing project")

        reasons = self._score_reasons(project, benchmark_metrics=benchmark.metrics)
        score = min(sum(reason.score for reason in reasons), 100)
        actions = self._actions(reasons)
        rule_summary = RiskSummary(
            recommendations=actions,
            source="rules",
            text=self._rule_summary_text(reasons),
        )
        summary = await self._ai_summary(
            actor=actor,
            actions=actions,
            project=project,
            reasons=reasons,
            rule_summary=rule_summary,
            score=score,
        )
        return ProjectRiskResult(
            actions=actions,
            level=self._level(score),
            project_id=project_id,
            reasons=reasons,
            score=score,
            summary=summary,
        )

    def _score_reasons(
        self,
        project: BenchmarkProjectSnapshot,
        *,
        benchmark_metrics: tuple[BenchmarkMetric, ...],
    ) -> list[RiskReason]:
        reasons: list[RiskReason] = []
        delay_days = self._delay_days(project)
        if delay_days > 0:
            reasons.append(
                RiskReason(
                    code="schedule_delay",
                    message=f"计划完成时间已逾期 {delay_days} 天",
                    score=min(30, delay_days * 2),
                    severity="high" if delay_days >= 15 else "medium",
                ),
            )

        budget_variance = self._budget_variance_percent(project)
        if budget_variance > 10:
            reasons.append(
                RiskReason(
                    code="budget_variance",
                    message=f"预算偏差达到 {budget_variance:.2f}%",
                    score=min(25, 10 + int((budget_variance - 10) * 0.5)),
                    severity="high" if budget_variance >= 30 else "medium",
                ),
            )

        overdue_rate = self._task_overdue_rate(project)
        if overdue_rate > 0:
            reasons.append(
                RiskReason(
                    code="task_overdue",
                    message=f"任务逾期率达到 {overdue_rate:.2f}%",
                    score=min(25, max(5, int(overdue_rate * 0.4))),
                    severity="high" if overdue_rate >= 40 else "medium",
                ),
            )

        metric_lookup = {metric.key: metric for metric in benchmark_metrics}
        cycle_metric = metric_lookup.get("cycle_days")
        if (
            cycle_metric is not None
            and cycle_metric.current_value is not None
            and cycle_metric.p90 is not None
            and cycle_metric.current_value > cycle_metric.p90
        ):
            reasons.append(
                RiskReason(
                    code="benchmark_cycle",
                    message="项目周期高于同类样本 P90",
                    score=10,
                    severity="medium",
                ),
            )

        phase_metric = metric_lookup.get("phase_stay_days")
        if (
            phase_metric is not None
            and phase_metric.current_value is not None
            and phase_metric.p90 is not None
            and phase_metric.current_value > phase_metric.p90
        ):
            reasons.append(
                RiskReason(
                    code="phase_stay",
                    message="环节停留时间高于同类样本 P90",
                    score=10,
                    severity="medium",
                ),
            )
        return reasons

    async def _ai_summary(
        self,
        *,
        actor: User,
        actions: list[str],
        project: BenchmarkProjectSnapshot,
        reasons: list[RiskReason],
        rule_summary: RiskSummary,
        score: int,
    ) -> RiskSummary:
        if self._ai_service is None:
            return rule_summary
        prompt = self._ai_prompt(project=project, reasons=reasons, actions=actions, score=score)
        try:
            result = await self._ai_service.complete_json(
                actor_id=actor.id,
                prompt=prompt,
                purpose="risk_summary",
                schema_name="risk_summary",
            )
        except (AiProviderDisabledError, AiProviderError, AiSchemaValidationError):
            return rule_summary
        return RiskSummary(
            recommendations=self._ai_recommendations(result.get("recommendations")),
            source="ai",
            text=str(result["summary"]),
        )

    def _delay_days(self, project: BenchmarkProjectSnapshot) -> int:
        end_date = (project.closed_at or self._now_provider()).date()
        return max((end_date - project.expected_finish_date).days, 0)

    @staticmethod
    def _budget_variance_percent(project: BenchmarkProjectSnapshot) -> float:
        if project.total_budget == 0:
            return 0
        variance = (project.spent_amount - project.total_budget) / project.total_budget * 100
        return max(float(variance), 0)

    @staticmethod
    def _task_overdue_rate(project: BenchmarkProjectSnapshot) -> float:
        if project.task_count == 0:
            return 0
        return project.overdue_task_count / project.task_count * 100

    @staticmethod
    def _actions(reasons: list[RiskReason]) -> list[str]:
        actions: list[str] = []
        reason_codes = {reason.code for reason in reasons}
        if "budget_variance" in reason_codes:
            actions.append("建议复核预算和付款计划")
        if "schedule_delay" in reason_codes or "phase_stay" in reason_codes:
            actions.append("建议重新确认关键节点负责人和完成日期")
        if "task_overdue" in reason_codes:
            actions.append("建议压实逾期任务责任人")
        return actions or ["继续按计划监控项目进展"]

    @staticmethod
    def _ai_recommendations(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    @staticmethod
    def _level(score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 30:
            return "medium"
        return "low"

    @staticmethod
    def _rule_summary_text(reasons: list[RiskReason]) -> str:
        if not reasons:
            return "暂无明显风险，继续按计划推进。"
        return "；".join(reason.message for reason in reasons)

    @staticmethod
    def _ai_prompt(
        *,
        actions: list[str],
        project: BenchmarkProjectSnapshot,
        reasons: list[RiskReason],
        score: int,
    ) -> str:
        reason_text = "; ".join(reason.message for reason in reasons) or "暂无明显风险"
        action_text = "; ".join(actions)
        return (
            f"Project {project.project_no} risk score is {score}. "
            f"Rule reasons: {reason_text}. Recommended actions: {action_text}. "
            "Return JSON with summary and recommendations."
        )
