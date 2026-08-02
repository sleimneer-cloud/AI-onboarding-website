from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.exception_handlers import register_exception_handlers
from app.db.dependencies import get_session_factory
from app.main import create_app


@pytest.fixture
def auth_contract_app(tmp_path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://ignored:ignored@127.0.0.1:1/ignored_test",
    )
    settings = Settings(
        _env_file=None,
        app_env="test",
        app_origin="http://test",
        database_url=None,
        session_secret="s" * 32,
        frontend_dist_dir=tmp_path / "dist",
    )
    return create_app(settings)


@pytest_asyncio.fixture
async def auth_contract_client(auth_contract_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=auth_contract_app),
        base_url="http://test",
    ) as client:
        yield client


def _assert_api_error(response, *, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    payload = response.json()
    assert set(payload) == {"error"}
    assert payload["error"]["code"] == code
    assert payload["error"]["field_errors"] == []
    assert payload["error"]["details"] == {}
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_login_checks_origin_before_database(
    auth_contract_client: AsyncClient,
) -> None:
    response = await auth_contract_client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.test", "password": "secret"},
    )
    _assert_api_error(response, status_code=403, code="ORIGIN_FORBIDDEN")


async def test_login_reports_unconfigured_database_without_details(
    auth_contract_client: AsyncClient,
) -> None:
    response = await auth_contract_client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://test"},
        json={"email": "person@example.test", "password": "secret"},
    )
    _assert_api_error(response, status_code=503, code="DATABASE_UNAVAILABLE")


async def test_invalid_json_uses_contract_error_shape(
    auth_contract_app: FastAPI,
) -> None:
    auth_contract_app.dependency_overrides[get_session_factory] = lambda: object()
    async with AsyncClient(
        transport=ASGITransport(app=auth_contract_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://test", "Content-Type": "application/json"},
            content=b'{"email":',
        )

    _assert_api_error(response, status_code=400, code="INVALID_JSON")


async def test_unknown_login_fields_are_rejected_without_echoing_input(
    auth_contract_app: FastAPI,
) -> None:
    auth_contract_app.dependency_overrides[get_session_factory] = lambda: object()
    secret_password = "NeverLogThisPassword!"
    async with AsyncClient(
        transport=ASGITransport(app=auth_contract_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://test"},
            json={
                "email": "person@example.test",
                "password": secret_password,
                "role": "hr",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["field_errors"][0]["field"] == "role"
    assert secret_password not in response.text


async def test_unknown_api_path_uses_hidden_not_found_shape(
    auth_contract_client: AsyncClient,
) -> None:
    response = await auth_contract_client.get("/api/v1/auth/not-a-route")
    _assert_api_error(response, status_code=404, code="RESOURCE_NOT_FOUND")


async def test_unhandled_error_hides_exception_message_and_logs_only_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    sensitive_message = "database failure for secret-user@example.test"

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError(sensitive_message)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert sensitive_message not in response.text
    assert sensitive_message not in caplog.text
    assert "exception_type=RuntimeError" in caplog.text
