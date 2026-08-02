from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from app.core.config import Settings, get_settings
from app.core.errors import ApiProblem
from app.db.dependencies import SessionFactory
from app.models.enums import UserRole
from app.security.cookies import session_cookie_policy
from app.security.passwords import get_password_manager
from app.security.requests import enforce_origin
from app.services.auth import AuthContext, AuthService


def get_auth_service(
    session_factory: SessionFactory,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(
        session_factory=session_factory,
        settings=settings,
        password_manager=get_password_manager(),
    )


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_auth_context(
    request: Request,
    service: AuthServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthContext:
    cookie_name = session_cookie_policy(settings).name
    return await service.authenticate(request.cookies.get(cookie_name))


CurrentAuth = Annotated[AuthContext, Depends(get_current_auth_context)]


def require_same_origin(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    enforce_origin(request, settings)


async def require_csrf(
    context: CurrentAuth,
    service: AuthServiceDependency,
    _origin: Annotated[None, Depends(require_same_origin)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AuthContext:
    service.enforce_csrf_hash(context.csrf_token_hash, csrf_token)
    return context


CsrfProtectedAuth = Annotated[AuthContext, Depends(require_csrf)]


def enforce_role(context: AuthContext, allowed_roles: frozenset[UserRole]) -> None:
    if context.user.role not in allowed_roles:
        raise ApiProblem(
            status_code=403,
            code="ROLE_FORBIDDEN",
            message="접근 권한이 없습니다.",
        )


def require_roles(
    *allowed_roles: UserRole,
) -> Callable[[CurrentAuth], AuthContext]:
    allowed = frozenset(allowed_roles)
    if not allowed:
        raise ValueError("At least one role is required")

    async def dependency(context: CurrentAuth) -> AuthContext:
        enforce_role(context, allowed)
        return context

    return dependency


def ensure_resource_owner(resource_owner_id: UUID, current_user_id: UUID) -> None:
    if resource_owner_id != current_user_id:
        raise ApiProblem(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="리소스를 찾을 수 없습니다.",
        )
