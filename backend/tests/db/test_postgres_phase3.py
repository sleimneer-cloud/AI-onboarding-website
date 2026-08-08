from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import REPOSITORY_ROOT, Settings
from app.db.session import create_database_engine, create_session_factory, transaction
from app.main import create_app
from app.models.auth import AuthRateLimit, User
from app.models.enums import UserRole
from app.security.passwords import get_password_manager
from app.services.demo_data import reset_demo_data

pytestmark = pytest.mark.postgres

DEMO_PASSWORD = "Phase3TestPassword!"
SESSION_SECRET = "phase-3-test-session-secret-is-long-enough"
PEER_ADDRESS = "198.51.100.33"


def alembic_config() -> Config:
    return Config(str(REPOSITORY_ROOT / "backend" / "alembic.ini"))


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(database_url)
    if not parsed_url.drivername.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if "test" not in (parsed_url.database or "").lower():
        pytest.fail("Refusing Phase 3 tests outside a database named with 'test'")

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(alembic_config(), "head")
        yield database_url
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


@dataclass(frozen=True)
class EmployeeTestEnvironment:
    settings: Settings
    app: object
    client: AsyncClient

    @property
    def session_factory(self):
        return self.app.state.session_factory


@pytest_asyncio.fixture
async def employee_env(postgres_url: str) -> AsyncIterator[EmployeeTestEnvironment]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        app_origin="http://test",
        database_url=postgres_url,
        session_secret=SESSION_SECRET,
        demo_account_password=DEMO_PASSWORD,
        frontend_dist_dir=REPOSITORY_ROOT / "frontend" / "dist",
    )
    seed_engine = create_database_engine(settings)
    try:
        async with transaction(create_session_factory(seed_engine)) as session:
            await reset_demo_data(session, settings)
            await session.execute(delete(AuthRateLimit))
    finally:
        await seed_engine.dispose()

    app = create_app(settings)
    transport = ASGITransport(app=app, client=(PEER_ADDRESS, 43210))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield EmployeeTestEnvironment(settings=settings, app=app, client=client)

    await app.state.database_engine.dispose()


async def login_employee(env: EmployeeTestEnvironment, email: str = "employee@ix-demo.test"):
    response = await env.client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://test"},
        json={"email": email, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def mutation_headers(csrf_token: str) -> dict[str, str]:
    return {"Origin": "http://test", "X-CSRF-Token": csrf_token}


def evidence_payload(dashboard: dict, *, action_ids: list[str] | None = None) -> dict:
    return {
        "assignment_id": dashboard["assignment"]["id"],
        "assigned_action_ids": action_ids
        if action_ids is not None
        else [action["id"] for action in dashboard["actions"]],
        "performed_action": "HR 담당자 두 명을 인터뷰하고 문의 흐름을 정리했습니다.",
        "discovery": "FAQ 내용보다 문의 진입 경로의 분산이 더 큰 원인이었습니다.",
        "changed_judgment": "FAQ 추가보다 단일 문의 진입점을 먼저 제공하기로 했습니다.",
        "work_impact": "프로토타입 범위를 단일 진입점과 문의 분류로 줄였습니다.",
        "next_action": "다음 업무에서도 구현 전에 실제 사용자 흐름을 확인합니다.",
        "links": [
            {
                "external_url": "https://example.test/hr-interview-summary",
                "title": "허구 HR 인터뷰 요약",
                "description": "담당자 인터뷰 흐름을 정리한 허구 문서입니다.",
            }
        ],
    }


async def complete_last_action(
    env: EmployeeTestEnvironment,
    dashboard: dict,
    csrf_token: str,
) -> dict:
    action = dashboard["actions"][-1]
    response = await env.client.patch(
        f"/api/v1/assigned-actions/{action['id']}",
        headers=mutation_headers(csrf_token),
        json={"status": "completed", "version": action["version"]},
    )
    assert response.status_code == 200
    return response.json()


async def test_employee_dashboard_aggregates_week_assignment_and_progress(
    employee_env: EmployeeTestEnvironment,
) -> None:
    await login_employee(employee_env)

    response = await employee_env.client.get("/api/v1/employee/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["onboarding"]["week_number"] == 2
    assert payload["onboarding"]["stage"] == "guided"
    assert payload["onboarding"]["week_status"] == "in_progress"
    assert payload["core_value"]["code"] == "obsessive_curiosity"
    assert payload["assignment"]["status"] == "active"
    assert len(payload["actions"]) == 3
    assert payload["progress"] == {
        "completed_actions": 2,
        "total_actions": 3,
        "percentage": 67,
    }
    assert payload["evidence"] is None
    assert payload["permissions"] == {
        "can_update_actions": True,
        "can_submit_evidence": False,
    }


async def test_action_transition_is_versioned_and_idempotent(
    employee_env: EmployeeTestEnvironment,
) -> None:
    csrf_token = await login_employee(employee_env)
    dashboard = (await employee_env.client.get("/api/v1/employee/dashboard")).json()

    updated = await complete_last_action(employee_env, dashboard, csrf_token)
    assert updated["status"] == "completed"
    assert updated["version"] == 2
    assert updated["completed_at"] is not None

    repeated = await employee_env.client.patch(
        f"/api/v1/assigned-actions/{updated['id']}",
        headers=mutation_headers(csrf_token),
        json={"status": "completed", "version": 1},
    )
    assert repeated.status_code == 200
    assert repeated.json()["version"] == 2

    conflict_action = dashboard["actions"][0]
    conflict = await employee_env.client.patch(
        f"/api/v1/assigned-actions/{conflict_action['id']}",
        headers=mutation_headers(csrf_token),
        json={"status": "pending", "version": 999},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"

    refreshed = (await employee_env.client.get("/api/v1/employee/dashboard")).json()
    assert refreshed["progress"]["percentage"] == 100
    assert refreshed["permissions"]["can_submit_evidence"] is True


async def test_evidence_requires_all_required_actions(
    employee_env: EmployeeTestEnvironment,
) -> None:
    csrf_token = await login_employee(employee_env)
    dashboard = (await employee_env.client.get("/api/v1/employee/dashboard")).json()

    response = await employee_env.client.post(
        "/api/v1/evidence",
        headers=mutation_headers(csrf_token),
        json=evidence_payload(
            dashboard,
            action_ids=[action["id"] for action in dashboard["actions"][:2]],
        ),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUIRED_ACTIONS_INCOMPLETE"


async def test_evidence_creation_locks_actions_and_is_idempotency_safe(
    employee_env: EmployeeTestEnvironment,
) -> None:
    csrf_token = await login_employee(employee_env)
    dashboard = (await employee_env.client.get("/api/v1/employee/dashboard")).json()
    updated_action = await complete_last_action(employee_env, dashboard, csrf_token)
    refreshed = (await employee_env.client.get("/api/v1/employee/dashboard")).json()
    request_json = evidence_payload(refreshed)

    created = await employee_env.client.post(
        "/api/v1/evidence",
        headers=mutation_headers(csrf_token),
        json=request_json,
    )
    assert created.status_code == 201
    evidence = created.json()
    assert evidence["assignment_id"] == refreshed["assignment"]["id"]
    assert len(evidence["links"]) == 1

    fetched = await employee_env.client.get(f"/api/v1/evidence/{evidence['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == evidence

    locked = await employee_env.client.patch(
        f"/api/v1/assigned-actions/{updated_action['id']}",
        headers=mutation_headers(csrf_token),
        json={"status": "pending", "version": updated_action["version"]},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "ACTION_LOCKED_BY_EVIDENCE"

    duplicate = await employee_env.client.post(
        "/api/v1/evidence",
        headers=mutation_headers(csrf_token),
        json=request_json,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EVIDENCE_ALREADY_EXISTS"
    assert duplicate.json()["error"]["details"]["evidence_id"] == evidence["id"]

    dashboard_after = (await employee_env.client.get("/api/v1/employee/dashboard")).json()
    assert dashboard_after["onboarding"]["week_status"] == "evidence_submitted"
    assert dashboard_after["permissions"] == {
        "can_update_actions": False,
        "can_submit_evidence": False,
    }


async def test_evidence_rejects_mismatched_actions_and_non_http_links(
    employee_env: EmployeeTestEnvironment,
) -> None:
    csrf_token = await login_employee(employee_env)
    dashboard = (await employee_env.client.get("/api/v1/employee/dashboard")).json()
    await complete_last_action(employee_env, dashboard, csrf_token)
    refreshed = (await employee_env.client.get("/api/v1/employee/dashboard")).json()

    mismatched = await employee_env.client.post(
        "/api/v1/evidence",
        headers=mutation_headers(csrf_token),
        json=evidence_payload(refreshed, action_ids=[str(uuid4())]),
    )
    assert mismatched.status_code == 422
    assert mismatched.json()["error"]["code"] == "ACTION_ASSIGNMENT_MISMATCH"

    invalid_link_payload = evidence_payload(refreshed)
    invalid_link_payload["links"][0]["external_url"] = "file:///private/demo.txt"
    invalid_link = await employee_env.client.post(
        "/api/v1/evidence",
        headers=mutation_headers(csrf_token),
        json=invalid_link_payload,
    )
    assert invalid_link.status_code == 422
    assert invalid_link.json()["error"]["code"] == "INVALID_LINK_SCHEME"


async def test_another_employee_cannot_access_owned_action(
    employee_env: EmployeeTestEnvironment,
) -> None:
    await login_employee(employee_env)
    dashboard = (await employee_env.client.get("/api/v1/employee/dashboard")).json()
    employee_env.client.cookies.clear()

    other_email = f"other-{uuid4()}@ix-demo.test"
    other_user_id = uuid4()
    async with transaction(employee_env.session_factory) as session:
        session.add(
            User(
                id=other_user_id,
                name="다른 허구 직원",
                email=other_email,
                normalized_email=other_email,
                password_hash=get_password_manager().hash(DEMO_PASSWORD),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
        )

    try:
        csrf_token = await login_employee(employee_env, other_email)
        action = dashboard["actions"][0]
        response = await employee_env.client.patch(
            f"/api/v1/assigned-actions/{action['id']}",
            headers=mutation_headers(csrf_token),
            json={"status": "pending", "version": action["version"]},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    finally:
        async with transaction(employee_env.session_factory) as session:
            await session.execute(delete(User).where(User.id == other_user_id))
