from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.employee import require_employee, require_employee_csrf
from app.api.evidence_cards import get_evidence_card_service
from app.models.enums import AIProvider, EvidenceCardStatus, UserRole
from app.schemas.cards import (
    EvidenceCardGenerationResponse,
    EvidenceCardPermissionsResponse,
    EvidenceCardResponse,
)
from app.schemas.llm import CardContentV1
from app.services.auth import AuthContext, AuthenticatedUser
from app.services.evidence_cards import CardGenerationResult


def card_content() -> CardContentV1:
    return CardContentV1.model_validate(
        {
            "schema_version": "1.0",
            "key_actions": [
                {
                    "text": "담당자를 인터뷰했습니다.",
                    "source_refs": ["evidence.performed_action"],
                }
            ],
            "value_connection": {
                "text": "공식 가치 정의와 기록한 행동을 함께 확인했습니다.",
                "source_refs": ["core_value.definition", "evidence.performed_action"],
            },
            "evidence_summary": {
                "text": "인터뷰 기록을 근거로 사용했습니다.",
                "source_refs": ["evidence.performed_action"],
            },
            "discovery": {
                "text": "문의 경로가 분산되어 있었습니다.",
                "source_refs": ["evidence.discovery"],
            },
            "judgment_change": {
                "text": "단일 문의 진입점을 우선하기로 했습니다.",
                "source_refs": ["evidence.changed_judgment"],
            },
            "work_impact": {
                "text": "프로토타입 범위를 줄였습니다.",
                "source_refs": ["evidence.work_impact"],
            },
            "next_action": {
                "text": "다음에도 사용자 흐름을 먼저 확인합니다.",
                "source_refs": ["evidence.next_action"],
            },
            "grounding_warnings": [],
        }
    )


class FakeEvidenceCardService:
    def __init__(self) -> None:
        self.employee_id = uuid4()
        self.evidence_id = uuid4()
        self.card_id = uuid4()
        self.processing = False
        self.calls: list[tuple[str, dict[str, object]]] = []

    def response(
        self,
        *,
        status: EvidenceCardStatus = EvidenceCardStatus.USER_REVIEW,
        version: int = 1,
    ) -> EvidenceCardResponse:
        return EvidenceCardResponse(
            id=self.card_id,
            evidence_id=self.evidence_id,
            status=status,
            content=None if status is EvidenceCardStatus.AI_PROCESSING else card_content(),
            generation=EvidenceCardGenerationResponse(
                provider=None if status is EvidenceCardStatus.AI_PROCESSING else AIProvider.MOCK,
                model_name=None,
                prompt_version="v1",
                schema_version="1.0",
                latency_ms=None if status is EvidenceCardStatus.AI_PROCESSING else 2,
            ),
            version=version,
            confirmed_at=(
                datetime(2026, 8, 2, 6, tzinfo=UTC)
                if status is EvidenceCardStatus.USER_CONFIRMED
                else None
            ),
            manager_reviewed_at=None,
            permissions=EvidenceCardPermissionsResponse(
                can_edit=status is EvidenceCardStatus.USER_REVIEW,
                can_confirm=status is EvidenceCardStatus.USER_REVIEW,
                can_retry=status is EvidenceCardStatus.GENERATION_FAILED,
            ),
        )

    async def create_or_retry_card(self, **kwargs) -> CardGenerationResult:
        self.calls.append(("create", kwargs))
        if self.processing:
            return CardGenerationResult(
                card=self.response(status=EvidenceCardStatus.AI_PROCESSING),
                status_code=202,
                retry_after_seconds=1,
            )
        return CardGenerationResult(card=self.response(), status_code=201)

    async def get_card(self, **kwargs) -> EvidenceCardResponse:
        self.calls.append(("get", kwargs))
        return self.response()

    async def update_card(self, **kwargs) -> EvidenceCardResponse:
        self.calls.append(("update", kwargs))
        return self.response(version=2)

    async def confirm_card(self, **kwargs) -> EvidenceCardResponse:
        self.calls.append(("confirm", kwargs))
        return self.response(status=EvidenceCardStatus.USER_CONFIRMED, version=2)


@pytest.fixture
def card_api(test_app: FastAPI):
    service = FakeEvidenceCardService()
    context = AuthContext(
        session_id=uuid4(),
        user=AuthenticatedUser(
            id=service.employee_id,
            name="김가온",
            email="employee@ix-demo.test",
            role=UserRole.EMPLOYEE,
            is_active=True,
        ),
        csrf_token_hash="0" * 64,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_app.dependency_overrides[get_evidence_card_service] = lambda: service
    test_app.dependency_overrides[require_employee] = lambda: context
    test_app.dependency_overrides[require_employee_csrf] = lambda: context
    try:
        yield service
    finally:
        test_app.dependency_overrides.clear()


async def test_card_routes_follow_create_get_update_confirm_contract(
    client: AsyncClient,
    card_api: FakeEvidenceCardService,
) -> None:
    created = await client.post(f"/api/v1/evidence/{card_api.evidence_id}/card")
    assert created.status_code == 201
    assert created.json()["generation"]["provider"] == "mock"
    assert card_api.calls[0][1]["employee_id"] == card_api.employee_id

    fetched = await client.get(f"/api/v1/evidence-cards/{card_api.card_id}")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()

    updated = await client.patch(
        f"/api/v1/evidence-cards/{card_api.card_id}",
        json={"version": 1, "content": card_content().model_dump(mode="json")},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    confirmed = await client.post(
        f"/api/v1/evidence-cards/{card_api.card_id}/confirm",
        json={"version": 2},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "user_confirmed"


async def test_processing_create_returns_retry_after(
    client: AsyncClient,
    card_api: FakeEvidenceCardService,
) -> None:
    card_api.processing = True

    response = await client.post(f"/api/v1/evidence/{card_api.evidence_id}/card")

    assert response.status_code == 202
    assert response.headers["Retry-After"] == "1"
    assert response.json()["status"] == "ai_processing"


async def test_card_requests_reject_unknown_and_invalid_content_fields(
    client: AsyncClient,
    card_api: FakeEvidenceCardService,
) -> None:
    unknown = await client.post(
        f"/api/v1/evidence-cards/{card_api.card_id}/confirm",
        json={"version": 1, "unknown": True},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_content = card_content().model_dump(mode="json")
    invalid_content["unknown"] = True
    invalid = await client.patch(
        f"/api/v1/evidence-cards/{card_api.card_id}",
        json={"version": 1, "content": invalid_content},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "CARD_SCHEMA_INVALID"

    missing_content = await client.patch(
        f"/api/v1/evidence-cards/{card_api.card_id}",
        json={"version": 1},
    )
    assert missing_content.status_code == 422
    assert missing_content.json()["error"]["code"] == "CARD_SCHEMA_INVALID"
