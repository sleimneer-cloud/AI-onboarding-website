from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    ensure_resource_owner,
    get_current_auth_context,
    require_roles,
)
from app.core.exception_handlers import register_exception_handlers
from app.models.enums import UserRole
from app.services.auth import AuthContext, AuthenticatedUser


def _context(role: UserRole) -> AuthContext:
    return AuthContext(
        session_id=uuid4(),
        user=AuthenticatedUser(
            id=uuid4(),
            name="권한 테스트",
            email="authorization@ix-demo.test",
            role=role,
            is_active=True,
        ),
        csrf_token_hash="c" * 64,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _authorization_app(context: AuthContext) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_current_auth_context] = lambda: context

    @app.get("/employee-only")
    async def employee_only(
        current: Annotated[
            AuthContext,
            Depends(require_roles(UserRole.EMPLOYEE)),
        ],
    ) -> dict[str, str]:
        return {"role": current.user.role.value}

    @app.get("/employees/{owner_id}")
    async def employee_resource(
        owner_id: UUID,
        current: Annotated[
            AuthContext,
            Depends(require_roles(UserRole.EMPLOYEE)),
        ],
    ) -> dict[str, str]:
        ensure_resource_owner(owner_id, current.user.id)
        return {"owner_id": str(owner_id)}

    return app


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        (UserRole.EMPLOYEE, 200),
        (UserRole.MANAGER, 403),
        (UserRole.HR, 403),
    ],
)
async def test_role_dependency_enforces_employee_boundary(
    role: UserRole,
    expected_status: int,
) -> None:
    app = _authorization_app(_context(role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/employee-only")

    assert response.status_code == expected_status
    if expected_status == 403:
        assert response.json()["error"]["code"] == "ROLE_FORBIDDEN"


async def test_idor_returns_not_found_for_another_users_resource() -> None:
    context = _context(UserRole.EMPLOYEE)
    app = _authorization_app(context)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        own = await client.get(f"/employees/{context.user.id}")
        other = await client.get(f"/employees/{uuid4()}")

    assert own.status_code == 200
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
