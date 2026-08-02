from __future__ import annotations

from dataclasses import dataclass

from fastapi import Response

from app.core.config import Settings


@dataclass(frozen=True)
class SessionCookiePolicy:
    name: str
    secure: bool
    max_age: int


def session_cookie_policy(settings: Settings) -> SessionCookiePolicy:
    production = settings.app_env == "production"
    return SessionCookiePolicy(
        name="__Host-ix_session" if production else "ix_session",
        secure=production,
        max_age=settings.session_ttl_seconds,
    )


def set_session_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    policy = session_cookie_policy(settings)
    response.set_cookie(
        key=policy.name,
        value=raw_token,
        max_age=policy.max_age,
        path="/",
        secure=policy.secure,
        httponly=True,
        samesite="lax",
    )


def delete_session_cookie(response: Response, settings: Settings) -> None:
    policy = session_cookie_policy(settings)
    response.delete_cookie(
        key=policy.name,
        path="/",
        secure=policy.secure,
        httponly=True,
        samesite="lax",
    )
