from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class SessionFactories:
    primary_engine: AsyncEngine
    read_only_engine: AsyncEngine
    primary: async_sessionmaker[AsyncSession]
    read_only: async_sessionmaker[AsyncSession]


def create_session_factories(settings: Settings) -> SessionFactories:
    primary_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    read_only_engine = (
        primary_engine
        if settings.effective_read_database_url == settings.database_url
        else create_async_engine(settings.effective_read_database_url, pool_pre_ping=True)
    )
    return SessionFactories(
        primary_engine=primary_engine,
        read_only_engine=read_only_engine,
        primary=async_sessionmaker(primary_engine, expire_on_commit=False),
        read_only=async_sessionmaker(read_only_engine, expire_on_commit=False),
    )


settings = get_settings()
session_factories = create_session_factories(settings)
engine = session_factories.primary_engine
read_only_engine = session_factories.read_only_engine
AsyncSessionLocal = session_factories.primary
ReadOnlyAsyncSessionLocal = session_factories.read_only


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_read_db_session() -> AsyncIterator[AsyncSession]:
    async with ReadOnlyAsyncSessionLocal() as session:
        yield session
