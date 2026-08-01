from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import OnboardingStage, database_enum


class OnboardingProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_profiles"
    __table_args__ = (
        CheckConstraint(
            "demo_week_override IS NULL OR demo_week_override BETWEEN 1 AND 12",
            name="demo_week_override_range",
        ),
        Index("ix_onboarding_profiles_manager_id", "manager_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    job_role: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    manager_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    demo_week_override: Mapped[int | None] = mapped_column(SmallInteger)


class CoreValue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "core_values"
    __table_args__ = (
        CheckConstraint("display_order BETWEEN 1 AND 12", name="display_order_range"),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    short_description: Mapped[str] = mapped_column(String(300), nullable=False)
    full_description: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("true"),
    )


class CurriculumWeek(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "curriculum_weeks"
    __table_args__ = (
        CheckConstraint("week_number BETWEEN 1 AND 12", name="week_number_range"),
        CheckConstraint(
            "(week_number BETWEEN 1 AND 4 AND stage = 'guided') OR "
            "(week_number BETWEEN 5 AND 8 AND stage = 'assisted') OR "
            "(week_number BETWEEN 9 AND 12 AND stage = 'autonomous')",
            name="week_number_stage_match",
        ),
    )

    week_number: Mapped[int] = mapped_column(SmallInteger, nullable=False, unique=True)
    core_value_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_values.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    stage: Mapped[OnboardingStage] = mapped_column(
        database_enum(OnboardingStage, "onboarding_stage"),
        nullable=False,
    )


class OnboardingWeek(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "onboarding_weeks"
    __table_args__ = (
        CheckConstraint("week_number BETWEEN 1 AND 12", name="week_number_range"),
        CheckConstraint("ends_on >= starts_on", name="valid_date_range"),
        Index(
            "uq_onboarding_weeks_profile_id_week_number",
            "profile_id",
            "week_number",
            unique=True,
        ),
        Index("ix_onboarding_weeks_curriculum_week_id", "curriculum_week_id"),
        Index("ix_onboarding_weeks_core_value_id", "core_value_id"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    curriculum_week_id: Mapped[UUID] = mapped_column(
        ForeignKey("curriculum_weeks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    core_value_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_values.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stage: Mapped[OnboardingStage] = mapped_column(
        database_enum(OnboardingStage, "onboarding_stage"),
        nullable=False,
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
