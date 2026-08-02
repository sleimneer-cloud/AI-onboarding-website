from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import UserRole


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email_and_reject_blank(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("email must not be blank")
        return stripped


class UserResponse(StrictModel):
    id: UUID
    name: str
    email: str
    role: UserRole


class LoginResponse(StrictModel):
    user: UserResponse
    csrf_token: str
    expires_at: datetime
    default_path: str


class CsrfResponse(StrictModel):
    csrf_token: str
