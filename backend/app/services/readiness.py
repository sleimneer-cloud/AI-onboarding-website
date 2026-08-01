import asyncio
from contextlib import suppress
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.db.migrations import EXPECTED_DATABASE_REVISION
from app.db.session import normalize_database_url


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

        async def probe() -> bool:
            assert engine is not None
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                return revision == EXPECTED_DATABASE_REVISION

        return await asyncio.wait_for(
            probe(), timeout=settings.database_ready_timeout_seconds
        )
    except Exception:
        return False
    finally:
        if engine is not None:
            with suppress(Exception):
                await engine.dispose()
