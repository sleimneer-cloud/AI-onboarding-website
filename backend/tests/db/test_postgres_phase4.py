from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

from alembic import command
from app.api.evidence_cards import get_evidence_card_service
from app.core.config import REPOSITORY_ROOT, Settings
from app.db.session import create_database_engine, create_session_factory, transaction
from app.main import create_app
from app.models.auth import AuthRateLimit
from app.models.evidence import EvidenceCard
from app.services.demo_data import reset_demo_data
from app.services.evidence_cards import EvidenceCardService
from app.services.evidence_generation import (
    EvidenceGenerationOrchestrator,
    MockEvidenceGenerator,
)

pytestmark = pytest.mark.postgres

DEMO_PASSWORD = "Phase4TestPassword!"
SESSION_SECRET = "phase-4-test-session-secret-is-long-enough"


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
        pytest.fail("Refusing Phase 4 tests outside a database named with 'test'")

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
class CardTestEnvironment:
    settings: Settings
    app: object
    client: AsyncClient

    @property
    def session_factory(self):
        return self.app.state.session_factory


@pytest_asyncio.fixture
async def card_env(postgres_url: str) -> AsyncIterator[CardTestEnvironment]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        app_origin="http://test",
        database_url=postgres_url,
        session_secret=SESSION_SECRET,
        demo_account_password=DEMO_PASSWORD,
        ai_provider="mock",
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
    transport = ASGITransport(app=app, client=("198.51.100.44", 43210))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield CardTestEnvironment(settings=settings, app=app, client=client)

    app.dependency_overrides.clear()
    await app.state.database_engine.dispose()


async def prepare_evidence(env: CardTestEnvironment) -> tuple[str, dict]:
    login = await env.client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://test"},
        json={"email": "employee@ix-demo.test", "password": DEMO_PASSWORD},
    )
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    headers = {"Origin": "http://test", "X-CSRF-Token": csrf}
    dashboard = (await env.client.get("/api/v1/employee/dashboard")).json()
    last_action = dashboard["actions"][-1]
    completed = await env.client.patch(
        f"/api/v1/assigned-actions/{last_action['id']}",
        headers=headers,
        json={"status": "completed", "version": last_action["version"]},
    )
    assert completed.status_code == 200
    dashboard = (await env.client.get("/api/v1/employee/dashboard")).json()
    evidence = await env.client.post(
        "/api/v1/evidence",
        headers=headers,
        json={
            "assignment_id": dashboard["assignment"]["id"],
            "assigned_action_ids": [action["id"] for action in dashboard["actions"]],
            "performed_action": "HR 담당자 두 명을 인터뷰하고 문의 흐름을 정리했습니다.",
            "discovery": "FAQ보다 문의 진입 경로의 분산이 더 큰 원인이었습니다.",
            "changed_judgment": "FAQ 추가보다 단일 문의 진입점을 먼저 만들기로 했습니다.",
            "work_impact": "프로토타입 범위를 단일 진입점과 문의 분류로 줄였습니다.",
            "next_action": "다음 업무에서도 실제 사용자 흐름을 먼저 확인합니다.",
            "links": [
                {
                    "external_url": "https://example.test/private-source",
                    "title": "허구 인터뷰 요약",
                    "description": "담당자 인터뷰를 정리한 허구 문서입니다.",
                }
            ],
        },
    )
    assert evidence.status_code == 201
    return csrf, evidence.json()


def mutation_headers(csrf: str) -> dict[str, str]:
    return {"Origin": "http://test", "X-CSRF-Token": csrf}


async def test_mock_card_create_edit_confirm_preserves_generated_original(
    card_env: CardTestEnvironment,
) -> None:
    csrf, evidence = await prepare_evidence(card_env)
    created = await card_env.client.post(
        f"/api/v1/evidence/{evidence['id']}/card",
        headers=mutation_headers(csrf),
    )
    assert created.status_code == 201
    card = created.json()
    assert card["status"] == "user_review"
    assert card["generation"]["provider"] == "mock"
    assert card["generation"]["model_name"] is None
    assert "https://example.test" not in str(card["content"])

    edited_content = card["content"]
    edited_content["next_action"]["text"] = "다음 업무에서는 사용자 흐름을 먼저 문서로 정리합니다."
    updated = await card_env.client.patch(
        f"/api/v1/evidence-cards/{card['id']}",
        headers=mutation_headers(csrf),
        json={"version": card["version"], "content": edited_content},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    async with card_env.session_factory() as session:
        stored = await session.get(EvidenceCard, card["id"])
        assert stored.generated_content_json["next_action"]["text"] != edited_content[
            "next_action"
        ]["text"]
        assert stored.final_content_json["next_action"]["text"] == edited_content["next_action"][
            "text"
        ]

    confirmed = await card_env.client.post(
        f"/api/v1/evidence-cards/{card['id']}/confirm",
        headers=mutation_headers(csrf),
        json={"version": 2},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "user_confirmed"
    assert confirmed.json()["version"] == 3

    blocked = await card_env.client.patch(
        f"/api/v1/evidence-cards/{card['id']}",
        headers=mutation_headers(csrf),
        json={"version": 3, "content": edited_content},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "CARD_NOT_EDITABLE"

    repeated = await card_env.client.post(
        f"/api/v1/evidence-cards/{card['id']}/confirm",
        headers=mutation_headers(csrf),
        json={"version": 2},
    )
    assert repeated.status_code == 200
    assert repeated.json()["version"] == 3


async def test_card_rejects_version_conflict_and_unknown_source_reference(
    card_env: CardTestEnvironment,
) -> None:
    csrf, evidence = await prepare_evidence(card_env)
    card = (
        await card_env.client.post(
            f"/api/v1/evidence/{evidence['id']}/card",
            headers=mutation_headers(csrf),
        )
    ).json()

    conflict = await card_env.client.patch(
        f"/api/v1/evidence-cards/{card['id']}",
        headers=mutation_headers(csrf),
        json={"version": 999, "content": card["content"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"

    invalid_content = card["content"]
    invalid_content["discovery"]["source_refs"] = ["action:00000000-0000-4000-8000-000000000099"]
    invalid = await card_env.client.patch(
        f"/api/v1/evidence-cards/{card['id']}",
        headers=mutation_headers(csrf),
        json={"version": card["version"], "content": invalid_content},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "CARD_SOURCE_REF_INVALID"


class BlockingMockGenerator:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.delegate = MockEvidenceGenerator()

    async def generate(self, generation_input, *, timeout_seconds):
        self.started.set()
        await self.release.wait()
        return await self.delegate.generate(
            generation_input,
            timeout_seconds=timeout_seconds,
        )


class BrokenMockGenerator:
    async def generate(self, generation_input, *, timeout_seconds):
        del generation_input, timeout_seconds
        raise RuntimeError("deterministic mock unavailable")


async def test_generation_failed_card_can_be_retried(
    card_env: CardTestEnvironment,
) -> None:
    csrf, evidence = await prepare_evidence(card_env)
    failed_generator = EvidenceGenerationOrchestrator(
        settings=card_env.settings,
        groq_generator=None,
        mock_generator=BrokenMockGenerator(),
    )
    failed_service = EvidenceCardService(
        session_factory=card_env.session_factory,
        settings=card_env.settings,
        generator=failed_generator,
    )
    card_env.app.dependency_overrides[get_evidence_card_service] = lambda: failed_service

    failed = await card_env.client.post(
        f"/api/v1/evidence/{evidence['id']}/card",
        headers=mutation_headers(csrf),
    )
    assert failed.status_code == 201
    assert failed.json()["status"] == "generation_failed"
    assert failed.json()["permissions"]["can_retry"] is True

    retry_service = EvidenceCardService(
        session_factory=card_env.session_factory,
        settings=card_env.settings,
        generator=EvidenceGenerationOrchestrator(
            settings=card_env.settings,
            groq_generator=None,
        ),
    )
    card_env.app.dependency_overrides[get_evidence_card_service] = lambda: retry_service
    retried = await card_env.client.post(
        f"/api/v1/evidence/{evidence['id']}/card",
        headers=mutation_headers(csrf),
    )

    assert retried.status_code == 200
    assert retried.json()["status"] == "user_review"
    assert retried.json()["id"] == failed.json()["id"]


async def test_concurrent_generation_creates_one_card_and_reports_processing(
    card_env: CardTestEnvironment,
) -> None:
    csrf, evidence = await prepare_evidence(card_env)
    blocking_mock = BlockingMockGenerator()
    generator = EvidenceGenerationOrchestrator(
        settings=card_env.settings,
        groq_generator=None,
        mock_generator=blocking_mock,
    )
    service = EvidenceCardService(
        session_factory=card_env.session_factory,
        settings=card_env.settings,
        generator=generator,
    )
    card_env.app.dependency_overrides[get_evidence_card_service] = lambda: service

    first_task = asyncio.create_task(
        card_env.client.post(
            f"/api/v1/evidence/{evidence['id']}/card",
            headers=mutation_headers(csrf),
        )
    )
    await asyncio.wait_for(blocking_mock.started.wait(), timeout=2)
    processing = await card_env.client.post(
        f"/api/v1/evidence/{evidence['id']}/card",
        headers=mutation_headers(csrf),
    )
    blocking_mock.release.set()
    created = await asyncio.wait_for(first_task, timeout=2)

    assert created.status_code == 201
    assert processing.status_code == 202
    assert processing.headers["Retry-After"] == "1"
    assert processing.json()["id"] == created.json()["id"]

    async with card_env.session_factory() as session:
        card_ids = list((await session.scalars(select(EvidenceCard.id))).all())
        assert [str(card_id) for card_id in card_ids] == [created.json()["id"]]
