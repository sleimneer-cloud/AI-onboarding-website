from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.errors import ApiProblem
from app.models.enums import ActionStatus, EvidenceCardStatus
from app.models.onboarding import OnboardingProfile
from app.schemas.employee import EvidenceCreateRequest
from app.services.employee import (
    EmployeeService,
    calculate_overall_status,
    calculate_progress,
    calculate_week_number,
    derive_week_status,
)


def test_onboarding_status_and_week_calculation_are_bounded() -> None:
    profile = OnboardingProfile(start_date=date(2026, 7, 20), demo_week_override=None)

    assert calculate_overall_status(profile.start_date, date(2026, 7, 19)) == "not_started"
    assert calculate_overall_status(profile.start_date, date(2026, 7, 20)) == "active"
    assert calculate_overall_status(profile.start_date, date(2026, 10, 12)) == "completed"
    assert calculate_week_number(profile, date(2026, 7, 1)) == 1
    assert calculate_week_number(profile, date(2027, 1, 1)) == 12

    profile.demo_week_override = 7
    assert calculate_week_number(profile, date(2026, 7, 1)) == 7


def test_progress_rounds_to_contract_percentage() -> None:
    actions = [
        SimpleNamespace(status=ActionStatus.COMPLETED),
        SimpleNamespace(status=ActionStatus.COMPLETED),
        SimpleNamespace(status=ActionStatus.PENDING),
    ]

    progress = calculate_progress(actions)

    assert progress.completed_actions == 2
    assert progress.total_actions == 3
    assert progress.percentage == 67
    assert calculate_progress([]).percentage == 0


@pytest.mark.parametrize(
    ("card_status", "expected"),
    [
        (EvidenceCardStatus.MANAGER_REVIEWED, "completed"),
        (EvidenceCardStatus.USER_CONFIRMED, "awaiting_manager"),
        (EvidenceCardStatus.USER_REVIEW, "reviewing_card"),
        (EvidenceCardStatus.AI_PROCESSING, "generating_card"),
        (EvidenceCardStatus.GENERATION_FAILED, "generation_failed"),
    ],
)
def test_card_status_has_week_status_precedence(
    card_status: EvidenceCardStatus,
    expected: str,
) -> None:
    assert (
        derive_week_status(
            card_status=card_status,
            evidence_exists=True,
            completed_actions=2,
            assignment_exists=True,
            future_week=False,
        )
        == expected
    )


def test_evidence_request_rejects_unknown_fields_and_duplicate_actions() -> None:
    action_id = uuid4()
    valid = {
        "assignment_id": str(uuid4()),
        "assigned_action_ids": [str(action_id)],
        "performed_action": "담당자 인터뷰를 진행하고 흐름을 정리했습니다.",
        "discovery": "문의 진입 경로가 여러 곳으로 나뉘어 있었습니다.",
        "changed_judgment": "FAQ보다 단일 진입점을 먼저 만들기로 했습니다.",
        "work_impact": "프로토타입의 범위를 핵심 흐름으로 줄였습니다.",
        "next_action": "다음 업무에서도 사용자 흐름을 먼저 확인합니다.",
        "links": [],
    }

    with pytest.raises(ValidationError):
        EvidenceCreateRequest.model_validate({**valid, "unknown": "rejected"})
    with pytest.raises(ValidationError):
        EvidenceCreateRequest.model_validate(
            {**valid, "assigned_action_ids": [str(action_id), str(action_id)]}
        )


def test_invalid_link_scheme_uses_domain_error_without_fetching() -> None:
    payload = EvidenceCreateRequest(
        assignment_id=uuid4(),
        assigned_action_ids=[uuid4()],
        performed_action="담당자 인터뷰를 진행하고 흐름을 정리했습니다.",
        discovery="문의 진입 경로가 여러 곳으로 나뉘어 있었습니다.",
        changed_judgment="FAQ보다 단일 진입점을 먼저 만들기로 했습니다.",
        work_impact="프로토타입의 범위를 핵심 흐름으로 줄였습니다.",
        next_action="다음 업무에서도 사용자 흐름을 먼저 확인합니다.",
        links=[
            {
                "external_url": "file:///private/demo.txt",
                "title": "허구 문서",
                "description": "외부 접근 없이 설명만 저장하는 문서입니다.",
            }
        ],
    )

    with pytest.raises(ApiProblem) as invalid:
        EmployeeService._validate_link_schemes(payload)

    assert invalid.value.status_code == 422
    assert invalid.value.code == "INVALID_LINK_SCHEME"
