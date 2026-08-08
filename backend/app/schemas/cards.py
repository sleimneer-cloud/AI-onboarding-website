from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError

from app.models.enums import AIProvider, EvidenceCardStatus
from app.schemas.llm import CardContentV1, StrictModel


class EvidenceCardGenerationResponse(StrictModel):
    provider: AIProvider | None
    model_name: str | None
    prompt_version: str
    schema_version: str
    latency_ms: int | None = Field(default=None, ge=0)


class EvidenceCardPermissionsResponse(StrictModel):
    can_edit: bool
    can_confirm: bool
    can_retry: bool


class EvidenceCardResponse(StrictModel):
    id: UUID
    evidence_id: UUID
    status: EvidenceCardStatus
    content: CardContentV1 | None
    generation: EvidenceCardGenerationResponse
    version: int = Field(ge=1)
    confirmed_at: datetime | None
    manager_reviewed_at: datetime | None
    permissions: EvidenceCardPermissionsResponse


class EvidenceCardUpdateRequest(StrictModel):
    version: int = Field(ge=1)
    content: CardContentV1

    @field_validator("content", mode="before")
    @classmethod
    def convert_card_schema_errors(cls, value: Any) -> CardContentV1:
        try:
            return CardContentV1.model_validate(value)
        except ValidationError as exc:
            raise PydanticCustomError(
                "card_schema_invalid",
                "Evidence Card content does not match CardContentV1",
            ) from exc


class EvidenceCardConfirmRequest(StrictModel):
    version: int = Field(ge=1)
