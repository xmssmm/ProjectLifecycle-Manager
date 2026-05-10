from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

HTTP_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0)


def resolve_metrics_path(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path if isinstance(route_path, str) else request.url.path


class HttpMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry(auto_describe=True)
        self.request_total = Counter(
            "http_requests_total",
            "Total HTTP requests by method, route, and status code.",
            ("method", "path", "status_code"),
            registry=self.registry,
        )
        self.request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds by method, route, and status code.",
            ("method", "path", "status_code"),
            buckets=HTTP_DURATION_BUCKETS,
            registry=self.registry,
        )
        self.in_progress = Gauge(
            "http_requests_in_progress",
            "In-progress HTTP requests by method and path.",
            ("method", "path"),
            registry=self.registry,
        )

    def observe(
        self,
        *,
        method: str,
        path: str,
        status_code: str,
        duration_seconds: float,
    ) -> None:
        labels = {"method": method, "path": path, "status_code": status_code}
        self.request_total.labels(**labels).inc()
        self.request_duration.labels(**labels).observe(duration_seconds)

    def render(self) -> bytes:
        return generate_latest(self.registry)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, metrics: HttpMetrics) -> None:
        super().__init__(app)
        self._metrics = metrics

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        in_progress_path = request.url.path
        status_code = "500"
        started_at = perf_counter()
        self._metrics.in_progress.labels(method=method, path=in_progress_path).inc()
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        finally:
            duration_seconds = perf_counter() - started_at
            self._metrics.observe(
                method=method,
                path=resolve_metrics_path(request),
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
            self._metrics.in_progress.labels(method=method, path=in_progress_path).dec()


def create_http_metrics() -> HttpMetrics:
    return HttpMetrics()


__all__ = [
    "CONTENT_TYPE_LATEST",
    "HttpMetrics",
    "PrometheusMetricsMiddleware",
    "create_http_metrics",
]
