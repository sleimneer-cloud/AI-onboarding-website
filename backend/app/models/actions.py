from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ActionSourceKind,
    ActionStatus,
    AssignmentStatus,
    OnboardingStage,
    WorkType,
    database_enum,
)


class WorkAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_assignments"
    __table_args__ = (
        CheckConstraint("char_length(description) <= 2000", name="description_max_length"),
        Index("ix_work_assignments_employee_id_status", "employee_id", "status"),
        Index("ix_work_assignments_manager_id_status", "manager_id", "status"),
    )

    onboarding_week_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_weeks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    manager_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    work_type: Mapped[WorkType] = mapped_column(
        database_enum(WorkType, "work_type"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        database_enum(AssignmentStatus, "assignment_status"),
        nullable=False,
        server_default=text("'active'"),
    )
    seed_key: Mapped[str | None] = mapped_column(String(100), unique=True)


class ActionLibrary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "action_library"
    __table_args__ = (
        CheckConstraint("char_length(action_text) <= 1000", name="action_text_max_length"),
        CheckConstraint(
            "jsonb_typeof(recommended_evidence) = 'array' "
            "AND jsonb_array_length(recommended_evidence) <= 5",
            name="recommended_evidence_array",
        ),
        CheckConstraint(
            "char_length(completion_criteria) <= 1000",
            name="completion_criteria_max_length",
        ),
        Index(
            "ix_action_library_core_value_id_is_active_priority",
            "core_value_id",
            "is_active",
            "priority",
        ),
    )

    library_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    core_value_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_values.id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_role: Mapped[str | None] = mapped_column(String(50))
    work_type: Mapped[WorkType | None] = mapped_column(
        database_enum(WorkType, "work_type"),
    )
    onboarding_stage: Mapped[OnboardingStage | None] = mapped_column(
        database_enum(OnboardingStage, "onboarding_stage"),
    )
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    completion_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("100"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class AssignedAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assigned_actions"
    __table_args__ = (
        CheckConstraint(
            "source_kind <> 'library' OR source_action_id IS NOT NULL",
            name="library_source_required",
        ),
        CheckConstraint(
            "source_kind <> 'custom' OR created_by_user_id IS NOT NULL",
            name="custom_creator_required",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status = 'pending' AND completed_at IS NULL)",
            name="status_completed_at_match",
        ),
        CheckConstraint("char_length(action_text_snapshot) <= 1000", name="action_text_max_length"),
        CheckConstraint(
            "char_length(completion_criteria_snapshot) <= 1000",
            name="completion_criteria_max_length",
        ),
        CheckConstraint(
            "jsonb_typeof(recommended_evidence_snapshot) = 'array'",
            name="recommended_evidence_array",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index(
            "uq_assigned_actions_assignment_id_display_order",
            "assignment_id",
            "display_order",
            unique=True,
        ),
        Index("ix_assigned_actions_assignment_id_status", "assignment_id", "status"),
        Index("ix_assigned_actions_source_action_id", "source_action_id"),
        Index("ix_assigned_actions_created_by_user_id", "created_by_user_id"),
        Index(
            "uq_assigned_actions_assignment_id_source_action_id_library",
            "assignment_id",
            "source_action_id",
            unique=True,
            postgresql_where=text("source_kind = 'library'"),
        ),
    )

    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_kind: Mapped[ActionSourceKind] = mapped_column(
        database_enum(ActionSourceKind, "action_source_kind"),
        nullable=False,
    )
    source_action_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("action_library.id", ondelete="RESTRICT"),
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    action_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    completion_criteria_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_evidence_snapshot: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[ActionStatus] = mapped_column(
        database_enum(ActionStatus, "action_status"),
        nullable=False,
        server_default=text("'pending'"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
