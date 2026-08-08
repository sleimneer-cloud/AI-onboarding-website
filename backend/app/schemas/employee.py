from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    ActionStatus,
    AssignmentStatus,
    EvidenceCardStatus,
    OnboardingStage,
    WorkType,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmployeeOnboardingResponse(StrictModel):
    profile_id: UUID
    overall_status: Literal["not_started", "active", "completed"]
    week_number: int = Field(ge=1, le=12)
    stage: OnboardingStage
    week_status: Literal[
        "completed",
        "awaiting_manager",
        "reviewing_card",
        "generating_card",
        "generation_failed",
        "evidence_submitted",
        "in_progress",
        "ready",
        "not_configured",
        "locked",
    ]
    starts_on: date
    ends_on: date


class CoreValueSummaryResponse(StrictModel):
    id: UUID
    code: str
    name: str
    short_description: str


class AssignmentSummaryResponse(StrictModel):
    id: UUID
    title: str
    description: str
    work_type: WorkType
    start_date: date
    due_date: date
    status: AssignmentStatus


class AssignedActionDetailResponse(StrictModel):
    id: UUID
    text: str
    completion_criteria: str
    recommended_evidence: list[str]
    is_required: bool
    display_order: int
    status: ActionStatus
    completed_at: datetime | None
    version: int = Field(ge=1)


class ProgressResponse(StrictModel):
    completed_actions: int = Field(ge=0)
    total_actions: int = Field(ge=0)
    percentage: int = Field(ge=0, le=100)


class DashboardEvidenceSummaryResponse(StrictModel):
    id: UUID
    submitted_at: datetime


class DashboardEvidenceCardSummaryResponse(StrictModel):
    id: UUID
    status: EvidenceCardStatus


class EmployeeDashboardPermissionsResponse(StrictModel):
    can_update_actions: bool
    can_submit_evidence: bool


class EmployeeDashboardResponse(StrictModel):
    onboarding: EmployeeOnboardingResponse
    core_value: CoreValueSummaryResponse
    assignment: AssignmentSummaryResponse | None
    actions: list[AssignedActionDetailResponse]
    progress: ProgressResponse
    evidence: DashboardEvidenceSummaryResponse | None
    evidence_card: DashboardEvidenceCardSummaryResponse | None
    permissions: EmployeeDashboardPermissionsResponse


class AssignedActionUpdateRequest(StrictModel):
    status: ActionStatus
    version: int = Field(ge=1)


class AssignedActionResponse(StrictModel):
    id: UUID
    status: ActionStatus
    completed_at: datetime | None
    version: int = Field(ge=1)


class EvidenceLinkCreateRequest(StrictModel):
    external_url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)

    @field_validator("external_url", "title", "description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

class EvidenceCreateRequest(StrictModel):
    assignment_id: UUID
    assigned_action_ids: list[UUID] = Field(min_length=1, max_length=5)
    performed_action: str = Field(min_length=10, max_length=2000)
    discovery: str = Field(min_length=10, max_length=2000)
    changed_judgment: str = Field(min_length=10, max_length=2000)
    work_impact: str = Field(min_length=10, max_length=2000)
    next_action: str = Field(min_length=10, max_length=1000)
    links: list[EvidenceLinkCreateRequest] = Field(default_factory=list, max_length=3)

    @field_validator(
        "performed_action",
        "discovery",
        "changed_judgment",
        "work_impact",
        "next_action",
        mode="before",
    )
    @classmethod
    def strip_evidence_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("assigned_action_ids")
    @classmethod
    def reject_duplicate_action_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("assigned_action_ids must not contain duplicates")
        return value


class EvidenceLinkResponse(StrictModel):
    id: UUID
    external_url: str
    title: str
    description: str


class EvidenceResponse(StrictModel):
    id: UUID
    assignment_id: UUID
    assigned_action_ids: list[UUID]
    performed_action: str
    discovery: str
    changed_judgment: str
    work_impact: str
    next_action: str
    links: list[EvidenceLinkResponse]
    submitted_at: datetime
