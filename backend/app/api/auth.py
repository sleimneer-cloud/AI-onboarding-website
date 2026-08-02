from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.api.dependencies import (
    AuthServiceDependency,
    CurrentAuth,
    require_same_origin,
)
from app.core.config import Settings, get_settings
from app.schemas.auth import CsrfResponse, LoginRequest, LoginResponse, UserResponse
from app.schemas.errors import ApiErrorResponse
from app.security.cookies import (
    delete_session_cookie,
    session_cookie_policy,
    set_session_cookie,
)
from app.security.requests import direct_peer_address

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ERROR_RESPONSES = {
    400: {"model": ApiErrorResponse},
    401: {"model": ApiErrorResponse},
    403: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
    429: {"model": ApiErrorResponse},
    500: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}


def _user_response(context_user) -> UserResponse:
    return UserResponse(
        id=context_user.id,
        name=context_user.name,
        email=context_user.email,
        role=context_user.role,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_same_origin)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    result = await service.login(
        email=payload.email,
        password=payload.password,
        client_address=direct_peer_address(request),
    )
    set_session_cookie(response, result.raw_session_token, settings)
    response.headers["Cache-Control"] = "no-store"
    default_paths = {
        "employee": "/employee",
        "manager": "/manager",
        "hr": "/hr",
    }
    return LoginResponse(
        user=_user_response(result.user),
        csrf_token=result.raw_csrf_token,
        expires_at=result.expires_at,
        default_path=default_paths[result.user.role.value],
    )


@router.get(
    "/me",
    response_model=UserResponse,
    responses=ERROR_RESPONSES,
)
async def me(context: CurrentAuth) -> UserResponse:
    return _user_response(context.user)


@router.get(
    "/csrf",
    response_model=CsrfResponse,
    responses=ERROR_RESPONSES,
)
async def csrf(
    response: Response,
    context: CurrentAuth,
    service: AuthServiceDependency,
) -> CsrfResponse:
    raw_csrf_token = await service.rotate_csrf(context)
    response.headers["Cache-Control"] = "no-store"
    return CsrfResponse(csrf_token=raw_csrf_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_same_origin)],
)
async def logout(
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    cookie_name = session_cookie_policy(settings).name
    await service.logout(
        raw_session_token=request.cookies.get(cookie_name),
        raw_csrf_token=csrf_token,
    )
    delete_session_cookie(response, settings)
