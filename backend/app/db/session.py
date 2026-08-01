from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def normalize_database_url(database_url: str) -> str:
    """Return a SQLAlchemy URL using psycopg's async-capable PostgreSQL driver."""

    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    raise ValueError("DATABASE_URL must use a PostgreSQL scheme")


def configured_database_url(settings: Settings) -> str:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required for this command")
    return normalize_database_url(settings.database_url.get_secret_value())


def create_database_engine(
    settings: Settings,
    *,
    pool_pre_ping: bool = True,
    **engine_options: object,
) -> AsyncEngine:
    return create_async_engine(
        configured_database_url(settings),
        echo=False,
        pool_pre_ping=pool_pre_ping,
        **engine_options,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Give a service exclusive ownership of one short database transaction."""

    async with session_factory() as session, session.begin():
        yield session
