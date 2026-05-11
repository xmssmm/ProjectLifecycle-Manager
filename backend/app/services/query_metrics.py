from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from math import ceil
from time import perf_counter
from typing import Any

QueryOperation = Callable[[], Awaitable[Any]]
ResultCounter = Callable[[Any], int]
ResultSignature = Callable[[Any], object]


class QueryResultChangedError(RuntimeError):
    """Raised when repeated benchmark samples return different logical results."""


@dataclass(frozen=True)
class QueryCase:
    name: str
    label: str
    operation: QueryOperation
    result_counter: ResultCounter | None = None
    result_signature: ResultSignature | None = None
    budget_ms: float = 800


@dataclass(frozen=True)
class QueryMetric:
    name: str
    label: str
    samples: int
    result_count: int | None
    min_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    avg_ms: float
    budget_ms: float

    @property
    def passes_budget(self) -> bool:
        return self.p99_ms <= self.budget_ms


@dataclass(frozen=True)
class QueryMetricsReport:
    metrics: list[QueryMetric]


class QueryMetricsRecorder:
    def __init__(self, *, clock: Callable[[], float] = perf_counter) -> None:
        self._clock = clock

    async def measure(
        self,
        cases: Sequence[QueryCase],
        *,
        samples: int = 20,
        warmup: int = 3,
    ) -> QueryMetricsReport:
        if samples < 1:
            raise ValueError("samples must be at least 1")
        if warmup < 0:
            raise ValueError("warmup cannot be negative")

        metrics = [
            await self._measure_case(case, samples=samples, warmup=warmup)
            for case in cases
        ]
        return QueryMetricsReport(metrics=metrics)

    async def _measure_case(
        self,
        case: QueryCase,
        *,
        samples: int,
        warmup: int,
    ) -> QueryMetric:
        for _ in range(warmup):
            await case.operation()

        durations_ms: list[float] = []
        result_count: int | None = None
        expected_signature = _UnsetSignature

        for _ in range(samples):
            started_at = self._clock()
            result = await case.operation()
            duration_ms = round((self._clock() - started_at) * 1000, 3)
            durations_ms.append(duration_ms)

            if case.result_counter is not None and result_count is None:
                result_count = int(case.result_counter(result))
            if case.result_signature is not None:
                signature = case.result_signature(result)
                if expected_signature is _UnsetSignature:
                    expected_signature = signature
                elif signature != expected_signature:
                    raise QueryResultChangedError(
                        f"{case.name} returned different result signatures while measuring",
                    )

        ordered = sorted(durations_ms)
        return QueryMetric(
            name=case.name,
            label=case.label,
            samples=samples,
            result_count=result_count,
            min_ms=ordered[0],
            p50_ms=_percentile(ordered, 50),
            p95_ms=_percentile(ordered, 95),
            p99_ms=_percentile(ordered, 99),
            max_ms=ordered[-1],
            avg_ms=round(sum(ordered) / samples, 3),
            budget_ms=case.budget_ms,
        )


_UnsetSignature = object()


def _percentile(sorted_values: Sequence[float], percentile: int) -> float:
    if not sorted_values:
        raise ValueError("sorted_values cannot be empty")
    rank = ceil((percentile / 100) * len(sorted_values))
    return sorted_values[max(rank - 1, 0)]


def render_markdown_report(
    *,
    title: str,
    baseline_rows: Sequence[Mapping[str, object]],
    optimized_rows: Sequence[Mapping[str, object]],
    commands: Sequence[str],
) -> str:
    lines = [
        f"# {title}",
        "",
        "目标：关键查询 P99 <= 800ms。",
        "",
        "## 优化前",
        "",
        "| query_name | 查询 | P99 | 来源 |",
        "| --- | --- | ---: | --- |",
        *[_metric_row(row) for row in baseline_rows],
        "",
        "## 优化后",
        "",
        "| query_name | 查询 | P99 | 来源 |",
        "| --- | --- | ---: | --- |",
        *[_metric_row(row) for row in optimized_rows],
        "",
        "## 复测命令",
        "",
    ]
    lines.extend(f"- `{command}`" for command in commands)
    lines.append("")
    return "\n".join(lines)


def _metric_row(row: Mapping[str, object]) -> str:
    return (
        f"| {row['name']} | {row['label']} | "
        f"{_format_ms(row['p99_ms'])} | {row['source']} |"
    )


def _format_ms(value: object) -> str:
    numeric = float(value) if isinstance(value, int | float) else float(str(value))
    return f"{numeric:g}ms"
