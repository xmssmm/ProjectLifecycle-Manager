from __future__ import annotations

from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_prod_compose_defines_required_services_and_healthchecks() -> None:
    compose = yaml.safe_load((ROOT_DIR / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert {
        "nginx",
        "backend",
        "frontend",
        "postgres",
        "redis",
        "celery-worker",
        "celery-beat",
    }.issubset(services.keys())
    assert services["backend"]["command"][:3] == [
        "gunicorn",
        "app.main:app",
        "-k",
    ]
    assert services["backend"]["healthcheck"]["test"][0] == "CMD"
    assert services["frontend"]["build"]["dockerfile"] == "Dockerfile.prod"
    assert "http://127.0.0.1/" in services["frontend"]["healthcheck"]["test"]
    assert services["nginx"]["build"] == {"context": "./nginx", "dockerfile": "Dockerfile.prod"}
    assert services["nginx"]["ports"] == ["80:80", "443:443"]
    assert services["celery-worker"]["command"][3] == "worker"
    assert services["celery-beat"]["command"][3] == "beat"
    assert services["postgres"]["restart"] == "unless-stopped"


def test_prod_nginx_enables_https_rate_limit_gzip_and_static_cache() -> None:
    nginx_conf = (ROOT_DIR / "nginx" / "nginx.conf").read_text(encoding="utf-8")
    nginx_dockerfile = (ROOT_DIR / "nginx" / "Dockerfile.prod").read_text(encoding="utf-8")

    assert "apk add --no-cache openssl" in nginx_dockerfile
    assert "listen 443 ssl" in nginx_conf
    assert "ssl_certificate" in nginx_conf
    assert "limit_req_zone" in nginx_conf
    assert "limit_req zone=api" in nginx_conf
    assert "gzip on" in nginx_conf
    assert "Cache-Control" in nginx_conf
    assert "proxy_pass http://backend:8000" in nginx_conf
    assert "proxy_pass http://frontend:80" in nginx_conf
