import asyncio
from contextlib import suppress
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings


def normalize_database_url(database_url: str) -> str:
    """Convert common PostgreSQL URLs to SQLAlchemy's async psycopg driver URL."""

    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    raise ValueError("DATABASE_URL must use a PostgreSQL scheme")


async def check_database_ready(
    settings: Annotated[Settings, Depends(get_settings)],
) -> bool:
    """Run a lazy, time-bounded database probe without exposing connection errors."""

    if settings.database_url is None:
        return False

    engine: AsyncEngine | None = None
    try:
        database_url = normalize_database_url(settings.database_url.get_secret_value())
        engine = create_async_engine(database_url, poolclass=NullPool)

        async def probe() -> None:
            assert engine is not None
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

        await asyncio.wait_for(probe(), timeout=settings.database_ready_timeout_seconds)
        return True
    except Exception:
        return False
    finally:
        if engine is not None:
            with suppress(Exception):
                await engine.dispose()
