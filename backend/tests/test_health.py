from fastapi import FastAPI
from httpx import AsyncClient

from app.services.readiness import check_database_ready


async def test_health_returns_contract_payload_without_database_probe(
    client: AsyncClient,
    test_app: FastAPI,
) -> None:
    def fail_if_called() -> bool:
        raise AssertionError("/health must not call the readiness dependency")

    test_app.dependency_overrides[check_database_ready] = fail_if_called

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "ok",
        "service": "ix-value-loop",
        "version": "0.1.0",
    }


async def test_ready_returns_200_when_database_probe_succeeds(
    client: AsyncClient,
    test_app: FastAPI,
) -> None:
    test_app.dependency_overrides[check_database_ready] = lambda: True

    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


async def test_ready_returns_sanitized_503_when_database_probe_fails(
    client: AsyncClient,
    test_app: FastAPI,
) -> None:
    test_app.dependency_overrides[check_database_ready] = lambda: False

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}
    assert "DATABASE_URL" not in response.text


async def test_ready_is_unavailable_when_database_url_is_unset(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}
