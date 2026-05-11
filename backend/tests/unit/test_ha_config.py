from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db import create_session_factories
from app.core.redis import create_redis_client
from app.tasks.celery_app import create_celery_app

ROOT_DIR = Path(__file__).resolve().parents[3]
HA_DOC_PATH = ROOT_DIR / "docs" / "PRODUCTION_HA_DEPLOYMENT.md"


def session_factory_url_host(factory: async_sessionmaker[AsyncSession]) -> str | None:
    engine = cast(AsyncEngine, factory.kw["bind"])
    return engine.url.host


def test_default_ha_settings_preserve_single_instance_behavior() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://primary:pass@postgres:5432/project_mgmt",
        redis_url="redis://redis:6379/0",
    )

    assert settings.database_replica_url is None
    assert settings.effective_read_database_url == settings.database_url
    assert settings.redis_sentinel_enabled is False
    assert settings.redis_sentinel_host_tuples == []
    assert settings.effective_celery_broker_url == settings.redis_url
    assert settings.effective_celery_result_backend == settings.redis_url


def test_replica_url_creates_separate_read_only_session_factory() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://primary:pass@postgres-primary:5432/project_mgmt",
        database_replica_url="postgresql+asyncpg://readonly:pass@postgres-replica:5432/project_mgmt",
    )

    factories = create_session_factories(settings)

    assert session_factory_url_host(factories.primary) == "postgres-primary"
    assert session_factory_url_host(factories.read_only) == "postgres-replica"


def test_redis_sentinel_settings_parse_hosts_and_configure_celery() -> None:
    settings = Settings(
        redis_url="redis://redis:6379/0",
        redis_sentinel_enabled=True,
        redis_sentinel_hosts="redis-sentinel-1:26379,redis-sentinel-2:26379",
        redis_sentinel_master_name="management-master",
        redis_sentinel_db=2,
    )

    celery_app = create_celery_app(settings)

    assert settings.redis_sentinel_host_tuples == [
        ("redis-sentinel-1", 26379),
        ("redis-sentinel-2", 26379),
    ]
    assert settings.effective_celery_broker_url == (
        "sentinel://redis-sentinel-1:26379;sentinel://redis-sentinel-2:26379"
    )
    assert settings.effective_celery_result_backend == settings.effective_celery_broker_url
    assert celery_app.conf.broker_transport_options["master_name"] == "management-master"
    assert celery_app.conf.result_backend_transport_options["master_name"] == "management-master"


def test_create_redis_client_uses_sentinel_when_configured(monkeypatch: Any) -> None:
    from app.core import redis as redis_module

    created: dict[str, Any] = {}

    class FakeSentinel:
        def __init__(self, hosts: list[tuple[str, int]], **kwargs: Any) -> None:
            created["hosts"] = hosts
            created["kwargs"] = kwargs

        def master_for(self, master_name: str, **kwargs: Any) -> dict[str, Any]:
            created["master_name"] = master_name
            created["master_kwargs"] = kwargs
            return {"client": "sentinel-master"}

    monkeypatch.setattr(redis_module, "Sentinel", FakeSentinel)
    settings = Settings(
        redis_sentinel_enabled=True,
        redis_sentinel_hosts="redis-sentinel:26379",
        redis_sentinel_master_name="management-master",
        redis_sentinel_db=3,
        redis_sentinel_password="secret",
    )

    client = cast(Any, create_redis_client(settings))

    assert client == {"client": "sentinel-master"}
    assert created["hosts"] == [("redis-sentinel", 26379)]
    assert created["master_name"] == "management-master"
    assert created["master_kwargs"]["db"] == 3
    assert created["master_kwargs"]["password"] == "secret"


def test_prod_compose_exposes_ha_env_and_horizontal_replicas() -> None:
    compose = yaml.safe_load((ROOT_DIR / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    backend = services["backend"]
    worker = services["celery-worker"]

    assert backend["deploy"]["replicas"] == "${BACKEND_REPLICAS:-2}"
    assert worker["deploy"]["replicas"] == "${CELERY_WORKER_REPLICAS:-2}"
    for service in (backend, worker, services["celery-beat"]):
        environment = service["environment"]
        assert "DATABASE_REPLICA_URL" in environment
        assert "REDIS_SENTINEL_ENABLED" in environment
        assert "REDIS_SENTINEL_HOSTS" in environment
        assert "REDIS_SENTINEL_MASTER_NAME" in environment


def test_production_ha_deployment_doc_covers_failover_and_rollback() -> None:
    doc = HA_DOC_PATH.read_text(encoding="utf-8")

    for section in ("PostgreSQL 主从", "Redis Sentinel", "水平扩展", "滚动发布", "回滚"):
        assert section in doc
    for setting in (
        "DATABASE_REPLICA_URL",
        "REDIS_SENTINEL_HOSTS",
        "BACKEND_REPLICAS",
        "CELERY_WORKER_REPLICAS",
    ):
        assert setting in doc
