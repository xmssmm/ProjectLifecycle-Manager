from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_prod_compose_defines_monitoring_stack() -> None:
    compose = yaml.safe_load((ROOT_DIR / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert {
        "prometheus",
        "grafana",
        "celery-exporter",
        "postgres-exporter",
        "node-exporter",
    }.issubset(services.keys())
    assert "9090:9090" in services["prometheus"]["ports"]
    assert "./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro" in services[
        "prometheus"
    ]["volumes"]
    assert "./monitoring/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro" in services[
        "prometheus"
    ]["volumes"]
    assert services["grafana"]["ports"] == ["3000:3000"]
    assert "./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro" in services[
        "grafana"
    ]["volumes"]
    assert "./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro" in services[
        "grafana"
    ]["volumes"]
    assert services["celery-exporter"]["environment"]["CELERY_BROKER_URL"] == (
        "${CELERY_BROKER_URL:-redis://redis:6379/0}"
    )
    assert "DATA_SOURCE_NAME" in services["postgres-exporter"]["environment"]
    assert services["node-exporter"]["pid"] == "host"


def test_prometheus_scrapes_app_and_exporters_with_alert_rules() -> None:
    prometheus_config = yaml.safe_load(
        (ROOT_DIR / "monitoring" / "prometheus" / "prometheus.yml").read_text(encoding="utf-8"),
    )
    alerts = yaml.safe_load(
        (ROOT_DIR / "monitoring" / "prometheus" / "alerts.yml").read_text(encoding="utf-8"),
    )

    assert prometheus_config["rule_files"] == ["/etc/prometheus/alerts.yml"]
    jobs = {config["job_name"] for config in prometheus_config["scrape_configs"]}
    assert {"backend", "celery", "postgres", "node"}.issubset(jobs)

    rules = {
        rule["alert"]: rule["expr"]
        for group in alerts["groups"]
        for rule in group["rules"]
    }
    assert "histogram_quantile(0.99" in rules["ApiP99LatencyHigh"]
    assert "> 1.5" in rules["ApiP99LatencyHigh"]
    assert "> 0.01" in rules["ApiErrorRateHigh"]
    assert "> 100" in rules["CeleryQueueBacklogHigh"]


def test_grafana_provisions_four_monitoring_dashboards() -> None:
    dashboards_dir = ROOT_DIR / "monitoring" / "grafana" / "dashboards"
    expected_dashboards = {
        "api-performance.json": "API 性能",
        "celery-queue.json": "Celery 队列",
        "database-pool.json": "DB 连接池",
        "disk-usage.json": "磁盘",
    }

    for filename, expected_title in expected_dashboards.items():
        dashboard = json.loads((dashboards_dir / filename).read_text(encoding="utf-8"))
        assert dashboard["title"] == expected_title
        assert dashboard["panels"]

    provider = yaml.safe_load(
        (
            ROOT_DIR
            / "monitoring"
            / "grafana"
            / "provisioning"
            / "dashboards"
            / "dashboards.yml"
        ).read_text(encoding="utf-8"),
    )
    assert provider["providers"][0]["options"]["path"] == "/var/lib/grafana/dashboards"
