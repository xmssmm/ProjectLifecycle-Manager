from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

DOCKER_DESKTOP_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
if os.path.isdir(DOCKER_DESKTOP_BIN):
    os.environ["PATH"] = f"{DOCKER_DESKTOP_BIN}{os.pathsep}{os.environ.get('PATH', '')}"


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16") as container:
        yield container


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer("redis:7") as container:
        yield container


@pytest.fixture(scope="session")
def postgres_url(postgres_container: PostgresContainer) -> str:
    return normalize_asyncpg_url(str(postgres_container.get_connection_url()))


def normalize_asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture(scope="session")
def redis_url(redis_container: RedisContainer) -> str:
    host = str(redis_container.get_container_host_ip())
    port = str(redis_container.get_exposed_port(6379))
    return f"redis://{host}:{port}/0"
