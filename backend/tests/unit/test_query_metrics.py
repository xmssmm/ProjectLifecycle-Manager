from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.services.query_metrics import (
    QueryCase,
    QueryMetricsRecorder,
    QueryResultChangedError,
    render_markdown_report,
)


def ticking_clock(values: list[float]) -> Iterator[float]:
    yield from values


@pytest.mark.asyncio
async def test_query_metrics_recorder_measures_samples_and_ignores_warmup() -> None:
    calls: list[str] = []
    clock = ticking_clock([0.10, 0.11, 0.11, 0.13, 0.13, 0.16])

    async def list_main_projects() -> list[int]:
        calls.append("main-projects")
        return [1, 2, 3]

    recorder = QueryMetricsRecorder(clock=lambda: next(clock))

    report = await recorder.measure(
        [
            QueryCase(
                name="main_project_list",
                label="主项目列表",
                operation=list_main_projects,
                result_counter=len,
                budget_ms=800,
            ),
        ],
        samples=3,
        warmup=1,
    )

    metric = report.metrics[0]
    assert calls == ["main-projects", "main-projects", "main-projects", "main-projects"]
    assert metric.name == "main_project_list"
    assert metric.samples == 3
    assert metric.result_count == 3
    assert metric.min_ms == 10
    assert metric.p50_ms == 20
    assert metric.p95_ms == 30
    assert metric.p99_ms == 30
    assert metric.max_ms == 30
    assert metric.passes_budget is True


@pytest.mark.asyncio
async def test_query_metrics_recorder_rejects_changed_result_signatures() -> None:
    responses = iter([[1, 2], [1, 3]])
    clock = ticking_clock([0.00, 0.01, 0.01, 0.02])

    async def flapping_query() -> list[int]:
        return next(responses)

    recorder = QueryMetricsRecorder(clock=lambda: next(clock))

    with pytest.raises(QueryResultChangedError):
        await recorder.measure(
            [
                QueryCase(
                    name="sub_project_list",
                    label="子项目列表",
                    operation=flapping_query,
                    result_signature=tuple,
                    budget_ms=800,
                ),
            ],
            samples=2,
            warmup=0,
        )


def test_render_markdown_report_records_baseline_optimized_metrics_and_commands() -> None:
    markdown = render_markdown_report(
        title="T-4-PERF-04 性能基线",
        baseline_rows=[
            {
                "name": "main_project_list",
                "label": "主项目列表",
                "p99_ms": 1900,
                "source": "docs/perf-baseline.md",
            },
        ],
        optimized_rows=[
            {
                "name": "main_project_list",
                "label": "主项目列表",
                "p99_ms": 320,
                "source": "local query metric",
            },
        ],
        commands=["cd backend && python -B -m pytest -q tests/unit/test_query_metrics.py"],
    )

    assert "# T-4-PERF-04 性能基线" in markdown
    assert "main_project_list" in markdown
    assert "1900ms" in markdown
    assert "320ms" in markdown
    assert "P99 <= 800ms" in markdown
    assert "cd backend && python -B -m pytest -q tests/unit/test_query_metrics.py" in markdown
