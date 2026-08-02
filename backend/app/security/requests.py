from __future__ import annotations

import hmac

from fastapi import Request

from app.core.config import Settings
from app.core.errors import ApiProblem


def direct_peer_address(request: Request) -> str:
    """Use only ASGI's direct peer; never parse forwarding headers here."""

    client = request.scope.get("client")
    if not client:
        return "unavailable"
    return str(client[0])


def enforce_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin is None or not hmac.compare_digest(origin, settings.app_origin):
        raise ApiProblem(
            status_code=403,
            code="ORIGIN_FORBIDDEN",
            message="허용되지 않은 요청 출처입니다.",
        )
