from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.employee import (
    get_employee_service,
    require_employee,
    require_employee_csrf,
)
from app.models.enums import (
    ActionStatus,
    AssignmentStatus,
    OnboardingStage,
    UserRole,
    WorkType,
)
from app.schemas.employee import (
    AssignedActionDetailResponse,
    AssignedActionResponse,
    AssignmentSummaryResponse,
    CoreValueSummaryResponse,
    EmployeeDashboardPermissionsResponse,
    EmployeeDashboardResponse,
    EmployeeOnboardingResponse,
    EvidenceLinkResponse,
    EvidenceResponse,
    ProgressResponse,
)
from app.services.auth import AuthContext, AuthenticatedUser


class FakeEmployeeService:
    def __init__(self) -> None:
        self.employee_id = uuid4()
        self.assignment_id = uuid4()
        self.action_id = uuid4()
        self.evidence_id = uuid4()
        self.update_calls: list[dict[str, object]] = []
        self.evidence_calls: list[dict[str, object]] = []

    async def get_dashboard(self, employee_id: UUID) -> EmployeeDashboardResponse:
        assert employee_id == self.employee_id
        return EmployeeDashboardResponse(
            onboarding=EmployeeOnboardingResponse(
                profile_id=uuid4(),
                overall_status="active",
                week_number=2,
                stage=OnboardingStage.GUIDED,
                week_status="in_progress",
                starts_on=date(2026, 7, 27),
                ends_on=date(2026, 8, 2),
            ),
            core_value=CoreValueSummaryResponse(
                id=uuid4(),
                code="obsessive_curiosity",
                name="강박적 호기심",
                short_description="질문과 검증으로 문제의 본질을 탐색합니다.",
            ),
            assignment=AssignmentSummaryResponse(
                id=self.assignment_id,
                title="허구 HR 문의 분석",
                description="반복 문의의 원인을 확인하는 허구 업무입니다.",
                work_type=WorkType.PROTOTYPE_BUILD,
                start_date=date(2026, 7, 27),
                due_date=date(2026, 8, 2),
                status=AssignmentStatus.ACTIVE,
            ),
            actions=[
                AssignedActionDetailResponse(
                    id=self.action_id,
                    text="사용자 흐름을 확인한다.",
                    completion_criteria="확인 기록이 있다.",
                    recommended_evidence=["인터뷰 기록"],
                    is_required=True,
                    display_order=1,
                    status=ActionStatus.PENDING,
                    completed_at=None,
                    version=1,
                )
            ],
            progress=ProgressResponse(
                completed_actions=0,
                total_actions=1,
                percentage=0,
            ),
            evidence=None,
            evidence_card=None,
            permissions=EmployeeDashboardPermissionsResponse(
                can_update_actions=True,
                can_submit_evidence=False,
            ),
        )

    async def update_action(self, **kwargs) -> AssignedActionResponse:
        self.update_calls.append(kwargs)
        return AssignedActionResponse(
            id=self.action_id,
            status=ActionStatus.COMPLETED,
            completed_at=datetime(2026, 8, 2, 4, tzinfo=UTC),
            version=2,
        )

    async def create_evidence(self, **kwargs) -> EvidenceResponse:
        self.evidence_calls.append(kwargs)
        payload = kwargs["payload"]
        return EvidenceResponse(
            id=self.evidence_id,
            assignment_id=self.assignment_id,
            assigned_action_ids=payload.assigned_action_ids,
            performed_action=payload.performed_action,
            discovery=payload.discovery,
            changed_judgment=payload.changed_judgment,
            work_impact=payload.work_impact,
            next_action=payload.next_action,
            links=[
                EvidenceLinkResponse(
                    id=uuid4(),
                    external_url=link.external_url,
                    title=link.title,
                    description=link.description,
                )
                for link in payload.links
            ],
            submitted_at=datetime(2026, 8, 2, 5, tzinfo=UTC),
        )

    async def get_evidence(self, **kwargs) -> EvidenceResponse:
        assert kwargs["employee_id"] == self.employee_id
        assert kwargs["evidence_id"] == self.evidence_id
        return EvidenceResponse(
            id=self.evidence_id,
            assignment_id=self.assignment_id,
            assigned_action_ids=[self.action_id],
            performed_action="담당자 인터뷰를 진행하고 흐름을 정리했습니다.",
            discovery="문의 진입 경로가 여러 곳으로 나뉘어 있었습니다.",
            changed_judgment="FAQ보다 단일 진입점을 먼저 만들기로 했습니다.",
            work_impact="프로토타입의 범위를 핵심 흐름으로 줄였습니다.",
            next_action="다음 업무에서도 사용자 흐름을 먼저 확인합니다.",
            links=[],
            submitted_at=datetime(2026, 8, 2, 5, tzinfo=UTC),
        )


@pytest.fixture
def employee_api(test_app: FastAPI):
    service = FakeEmployeeService()
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
    test_app.dependency_overrides[get_employee_service] = lambda: service
    test_app.dependency_overrides[require_employee] = lambda: context
    test_app.dependency_overrides[require_employee_csrf] = lambda: context
    try:
        yield service
    finally:
        test_app.dependency_overrides.clear()


def evidence_payload(service: FakeEmployeeService) -> dict[str, object]:
    return {
        "assignment_id": str(service.assignment_id),
        "assigned_action_ids": [str(service.action_id)],
        "performed_action": "담당자 인터뷰를 진행하고 흐름을 정리했습니다.",
        "discovery": "문의 진입 경로가 여러 곳으로 나뉘어 있었습니다.",
        "changed_judgment": "FAQ보다 단일 진입점을 먼저 만들기로 했습니다.",
        "work_impact": "프로토타입의 범위를 핵심 흐름으로 줄였습니다.",
        "next_action": "다음 업무에서도 사용자 흐름을 먼저 확인합니다.",
        "links": [],
    }


async def test_dashboard_and_evidence_routes_follow_contract(
    client: AsyncClient,
    employee_api: FakeEmployeeService,
) -> None:
    dashboard = await client.get("/api/v1/employee/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["onboarding"]["week_number"] == 2
    assert dashboard.json()["actions"][0]["version"] == 1

    updated = await client.patch(
        f"/api/v1/assigned-actions/{employee_api.action_id}",
        json={"status": "completed", "version": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"
    assert employee_api.update_calls[0]["employee_id"] == employee_api.employee_id

    created = await client.post("/api/v1/evidence", json=evidence_payload(employee_api))
    assert created.status_code == 201
    assert created.json()["id"] == str(employee_api.evidence_id)

    fetched = await client.get(f"/api/v1/evidence/{employee_api.evidence_id}")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


async def test_employee_requests_reject_unknown_fields(
    client: AsyncClient,
    employee_api: FakeEmployeeService,
) -> None:
    action = await client.patch(
        f"/api/v1/assigned-actions/{employee_api.action_id}",
        json={"status": "completed", "version": 1, "unknown": True},
    )
    assert action.status_code == 422
    assert action.json()["error"]["code"] == "VALIDATION_ERROR"

    evidence = await client.post(
        "/api/v1/evidence",
        json={**evidence_payload(employee_api), "unknown": True},
    )
    assert evidence.status_code == 422
    assert evidence.json()["error"]["code"] == "VALIDATION_ERROR"
