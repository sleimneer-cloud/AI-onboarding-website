from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import OnboardingStage, WorkType


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationCoreValueV1(StrictModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=100)
    definition: str = Field(max_length=2000)


class GenerationOnboardingV1(StrictModel):
    week_number: int = Field(ge=1, le=12)
    stage: OnboardingStage


class GenerationAssignmentV1(StrictModel):
    id: UUID
    title: str = Field(max_length=200)
    description: str = Field(max_length=2000)
    work_type: WorkType
    description_source_ref: Literal["assignment.description"]


class GenerationActionV1(StrictModel):
    id: UUID
    text: str = Field(max_length=1000)
    completion_criteria: str = Field(max_length=1000)
    source_ref: str = Field(pattern=r"^action:[0-9a-fA-F-]{36}$")


class GenerationEvidenceFieldV1(StrictModel):
    text: str = Field(min_length=10, max_length=2000)
    source_ref: str


class GenerationNextActionFieldV1(StrictModel):
    text: str = Field(min_length=10, max_length=1000)
    source_ref: Literal["evidence.next_action"]


class GenerationLinkV1(StrictModel):
    id: UUID
    title: str = Field(max_length=200)
    description: str = Field(max_length=1000)
    source_ref: str = Field(pattern=r"^link:[0-9a-fA-F-]{36}$")


class GenerationEvidenceV1(StrictModel):
    id: UUID
    performed_action: GenerationEvidenceFieldV1
    discovery: GenerationEvidenceFieldV1
    changed_judgment: GenerationEvidenceFieldV1
    work_impact: GenerationEvidenceFieldV1
    next_action: GenerationNextActionFieldV1
    links: list[GenerationLinkV1] = Field(max_length=3)


class EvidenceCardGenerationInputV1(StrictModel):
    schema_version: Literal["1.0"]
    request_id: UUID
    language: Literal["ko-KR"]
    core_value: GenerationCoreValueV1
    onboarding: GenerationOnboardingV1
    assignment: GenerationAssignmentV1
    actions: list[GenerationActionV1] = Field(min_length=1, max_length=5)
    evidence: GenerationEvidenceV1

    def allowed_source_refs(self) -> frozenset[str]:
        return frozenset(
            {
                "core_value.definition",
                self.assignment.description_source_ref,
                *(action.source_ref for action in self.actions),
                self.evidence.performed_action.source_ref,
                self.evidence.discovery.source_ref,
                self.evidence.changed_judgment.source_ref,
                self.evidence.work_impact.source_ref,
                self.evidence.next_action.source_ref,
                *(link.source_ref for link in self.evidence.links),
            }
        )


class CardTextV1(StrictModel):
    text: str = Field(min_length=1, max_length=500)
    source_refs: list[str] = Field(min_length=1)

    @field_validator("source_refs")
    @classmethod
    def reject_duplicate_source_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("source_refs must not contain duplicates")
        return value


class CardKeyActionV1(CardTextV1):
    text: str = Field(min_length=1, max_length=300)


class CardEvidenceSummaryV1(CardTextV1):
    text: str = Field(min_length=1, max_length=600)


GroundingField = Literal[
    "key_actions",
    "value_connection",
    "evidence_summary",
    "discovery",
    "judgment_change",
    "work_impact",
    "next_action",
]


class GroundingWarningV1(StrictModel):
    field: GroundingField
    message: str = Field(min_length=1, max_length=300)
    source_refs: list[str] = Field(min_length=1)

    @field_validator("source_refs")
    @classmethod
    def reject_duplicate_source_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("source_refs must not contain duplicates")
        return value


class CardContentV1(StrictModel):
    schema_version: Literal["1.0"]
    key_actions: list[CardKeyActionV1] = Field(min_length=1, max_length=5)
    value_connection: CardTextV1
    evidence_summary: CardEvidenceSummaryV1
    discovery: CardTextV1
    judgment_change: CardTextV1
    work_impact: CardTextV1
    next_action: CardTextV1
    grounding_warnings: list[GroundingWarningV1] = Field(max_length=7)

    def all_source_refs(self) -> list[str]:
        groups = [
            *(item.source_refs for item in self.key_actions),
            self.value_connection.source_refs,
            self.evidence_summary.source_refs,
            self.discovery.source_refs,
            self.judgment_change.source_refs,
            self.work_impact.source_refs,
            self.next_action.source_refs,
            *(warning.source_refs for warning in self.grounding_warnings),
        ]
        return [source_ref for group in groups for source_ref in group]


class CardSourceReferenceError(ValueError):
    pass


def validate_card_source_refs(
    content: CardContentV1,
    allowed_source_refs: frozenset[str],
) -> None:
    invalid_refs = sorted(set(content.all_source_refs()) - allowed_source_refs)
    if invalid_refs:
        raise CardSourceReferenceError("Card contains source references absent from its input")
