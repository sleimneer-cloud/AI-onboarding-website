from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AIProvider, EvidenceCardStatus, database_enum


class EvidenceSubmission(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "evidence_submissions"
    __table_args__ = (
        CheckConstraint(
            "char_length(performed_action) BETWEEN 10 AND 2000",
            name="performed_action_length",
        ),
        CheckConstraint("char_length(discovery) BETWEEN 10 AND 2000", name="discovery_length"),
        CheckConstraint(
            "char_length(changed_judgment) BETWEEN 10 AND 2000",
            name="changed_judgment_length",
        ),
        CheckConstraint(
            "char_length(work_impact) BETWEEN 10 AND 2000",
            name="work_impact_length",
        ),
        CheckConstraint(
            "char_length(next_action) BETWEEN 10 AND 1000",
            name="next_action_length",
        ),
        Index("ix_evidence_submissions_employee_id", "employee_id"),
    )

    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_assignments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    performed_action: Mapped[str] = mapped_column(Text, nullable=False)
    discovery: Mapped[str] = mapped_column(Text, nullable=False)
    changed_judgment: Mapped[str] = mapped_column(Text, nullable=False)
    work_impact: Mapped[str] = mapped_column(Text, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceSubmissionAction(Base):
    __tablename__ = "evidence_submission_actions"
    __table_args__ = (
        Index("ix_evidence_submission_actions_assigned_action_id", "assigned_action_id"),
    )

    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "evidence_submissions.id",
            name="fk_evidence_submission_actions_evidence",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    assigned_action_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "assigned_actions.id",
            name="fk_evidence_submission_actions_action",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )


class EvidenceLink(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "evidence_links"
    __table_args__ = (Index("ix_evidence_links_evidence_id", "evidence_id"),)

    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)


class EvidenceCard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evidence_cards"
    __table_args__ = (
        CheckConstraint("generation_attempts >= 0", name="generation_attempts_nonnegative"),
        CheckConstraint(
            "generation_latency_ms IS NULL OR generation_latency_ms >= 0",
            name="generation_latency_nonnegative",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_evidence_cards_status_updated_at", "status", "updated_at"),
    )

    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[EvidenceCardStatus] = mapped_column(
        database_enum(EvidenceCardStatus, "evidence_card_status"),
        nullable=False,
    )
    generated_content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    final_content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    generated_by: Mapped[AIProvider | None] = mapped_column(
        database_enum(AIProvider, "ai_provider"),
    )
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    generation_attempts: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("0"),
    )
    generation_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_error_code: Mapped[str | None] = mapped_column(String(50))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manager_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )


class ManagerFeedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "manager_feedbacks"
    __table_args__ = (
        CheckConstraint(
            "char_length(observed_behavior) BETWEEN 10 AND 1000",
            name="observed_behavior_length",
        ),
        CheckConstraint(
            "char_length(work_impact) BETWEEN 10 AND 1000",
            name="work_impact_length",
        ),
        CheckConstraint(
            "char_length(positive_feedback) BETWEEN 10 AND 1000",
            name="positive_feedback_length",
        ),
        CheckConstraint(
            "char_length(next_action) BETWEEN 10 AND 1000",
            name="next_action_length",
        ),
        Index("ix_manager_feedbacks_manager_id_submitted_at", "manager_id", "submitted_at"),
    )

    evidence_card_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence_cards.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    manager_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observed_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    work_impact: Mapped[str] = mapped_column(Text, nullable=False)
    positive_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
