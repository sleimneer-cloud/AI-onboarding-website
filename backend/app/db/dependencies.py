from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ApiProblem


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise ApiProblem(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="데이터베이스를 사용할 수 없습니다.",
        )
    return session_factory


SessionFactory = Annotated[
    async_sessionmaker[AsyncSession],
    Depends(get_session_factory),
]
