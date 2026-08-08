"""Create the Phase 1 PostgreSQL schema.

Revision ID: 20260802_0001
Revises: None
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260802_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM(
    "employee", "manager", "hr", name="user_role", create_type=False
)
onboarding_stage = postgresql.ENUM(
    "guided", "assisted", "autonomous", name="onboarding_stage", create_type=False
)
work_type = postgresql.ENUM(
    "user_interview",
    "process_analysis",
    "problem_definition",
    "data_analysis",
    "service_planning",
    "prototype_build",
    "user_validation",
    "collaboration",
    "result_improvement",
    name="work_type",
    create_type=False,
)
assignment_status = postgresql.ENUM(
    "active", "completed", "cancelled", name="assignment_status", create_type=False
)
action_source_kind = postgresql.ENUM(
    "library", "custom", name="action_source_kind", create_type=False
)
action_status = postgresql.ENUM(
    "pending", "completed", name="action_status", create_type=False
)
evidence_card_status = postgresql.ENUM(
    "ai_processing",
    "generation_failed",
    "user_review",
    "user_confirmed",
    "manager_reviewed",
    name="evidence_card_status",
    create_type=False,
)
ai_provider = postgresql.ENUM("groq", "mock", name="ai_provider", create_type=False)

enum_types = (
    user_role,
    onboarding_stage,
    work_type,
    assignment_status,
    action_source_kind,
    action_status,
    evidence_card_status,
    ai_provider,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in enum_types:
        enum_type.create(bind, checkfirst=False)

    op.create_table(
        "users",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("normalized_email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("demo_fixture_key", sa.String(length=100), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("demo_fixture_key", name="uq_users_demo_fixture_key"),
        sa.UniqueConstraint("normalized_email", name="uq_users_normalized_email"),
    )

    op.create_table(
        "auth_rate_limits",
        sa.Column("subject_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_count", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_auth_rate_limits"),
        sa.UniqueConstraint("subject_hash", name="uq_auth_rate_limits_subject_hash"),
    )
    op.create_index(
        "ix_auth_rate_limits_blocked_until", "auth_rate_limits", ["blocked_until"]
    )

    op.create_table(
        "auth_sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user_id_expires_at", "auth_sessions", ["user_id", "expires_at"]
    )

    op.create_table(
        "core_values",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("short_description", sa.String(length=300), nullable=False),
        sa.Column("full_description", sa.Text(), nullable=False),
        sa.Column("display_order", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "display_order BETWEEN 1 AND 12",
            name=op.f("ck_core_values_display_order_range"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_core_values"),
        sa.UniqueConstraint("code", name="uq_core_values_code"),
        sa.UniqueConstraint("display_order", name="uq_core_values_display_order"),
        sa.UniqueConstraint("name", name="uq_core_values_name"),
    )

    op.create_table(
        "onboarding_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_role", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("demo_week_override", sa.SmallInteger(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "demo_week_override IS NULL OR demo_week_override BETWEEN 1 AND 12",
            name=op.f("ck_onboarding_profiles_demo_week_override_range"),
        ),
        sa.ForeignKeyConstraint(
            ["manager_id"],
            ["users.id"],
            name="fk_onboarding_profiles_manager_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_onboarding_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_onboarding_profiles"),
        sa.UniqueConstraint("user_id", name="uq_onboarding_profiles_user_id"),
    )
    op.create_index(
        "ix_onboarding_profiles_manager_id", "onboarding_profiles", ["manager_id"]
    )

    op.create_table(
        "curriculum_weeks",
        sa.Column("week_number", sa.SmallInteger(), nullable=False),
        sa.Column("core_value_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", onboarding_stage, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "week_number BETWEEN 1 AND 12",
            name=op.f("ck_curriculum_weeks_week_number_range"),
        ),
        sa.CheckConstraint(
            "(week_number BETWEEN 1 AND 4 AND stage = 'guided') OR "
            "(week_number BETWEEN 5 AND 8 AND stage = 'assisted') OR "
            "(week_number BETWEEN 9 AND 12 AND stage = 'autonomous')",
            name=op.f("ck_curriculum_weeks_week_number_stage_match"),
        ),
        sa.ForeignKeyConstraint(
            ["core_value_id"],
            ["core_values.id"],
            name="fk_curriculum_weeks_core_value_id_core_values",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_curriculum_weeks"),
        sa.UniqueConstraint("core_value_id", name="uq_curriculum_weeks_core_value_id"),
        sa.UniqueConstraint("week_number", name="uq_curriculum_weeks_week_number"),
    )

    op.create_table(
        "onboarding_weeks",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_number", sa.SmallInteger(), nullable=False),
        sa.Column("curriculum_week_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("core_value_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", onboarding_stage, nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ends_on >= starts_on",
            name=op.f("ck_onboarding_weeks_valid_date_range"),
        ),
        sa.CheckConstraint(
            "week_number BETWEEN 1 AND 12",
            name=op.f("ck_onboarding_weeks_week_number_range"),
        ),
        sa.ForeignKeyConstraint(
            ["core_value_id"],
            ["core_values.id"],
            name="fk_onboarding_weeks_core_value_id_core_values",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_week_id"],
            ["curriculum_weeks.id"],
            name="fk_onboarding_weeks_curriculum_week_id_curriculum_weeks",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["onboarding_profiles.id"],
            name="fk_onboarding_weeks_profile_id_onboarding_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_onboarding_weeks"),
    )
    op.create_index(
        "ix_onboarding_weeks_core_value_id", "onboarding_weeks", ["core_value_id"]
    )
    op.create_index(
        "ix_onboarding_weeks_curriculum_week_id",
        "onboarding_weeks",
        ["curriculum_week_id"],
    )
    op.create_index(
        "uq_onboarding_weeks_profile_id_week_number",
        "onboarding_weeks",
        ["profile_id", "week_number"],
        unique=True,
    )

    op.create_table(
        "work_assignments",
        sa.Column("onboarding_week_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("work_type", work_type, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status", assignment_status, server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("seed_key", sa.String(length=100), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(description) <= 2000",
            name=op.f("ck_work_assignments_description_max_length"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["users.id"],
            name="fk_work_assignments_employee_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["manager_id"],
            ["users.id"],
            name="fk_work_assignments_manager_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["onboarding_week_id"],
            ["onboarding_weeks.id"],
            name="fk_work_assignments_onboarding_week_id_onboarding_weeks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_work_assignments"),
        sa.UniqueConstraint(
            "onboarding_week_id", name="uq_work_assignments_onboarding_week_id"
        ),
        sa.UniqueConstraint("seed_key", name="uq_work_assignments_seed_key"),
    )
    op.create_index(
        "ix_work_assignments_employee_id_status",
        "work_assignments",
        ["employee_id", "status"],
    )
    op.create_index(
        "ix_work_assignments_manager_id_status",
        "work_assignments",
        ["manager_id", "status"],
    )

    op.create_table(
        "action_library",
        sa.Column("library_key", sa.String(length=120), nullable=False),
        sa.Column("core_value_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_role", sa.String(length=50), nullable=True),
        sa.Column("work_type", work_type, nullable=True),
        sa.Column("onboarding_stage", onboarding_stage, nullable=True),
        sa.Column("action_text", sa.Text(), nullable=False),
        sa.Column("recommended_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("completion_criteria", sa.Text(), nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default=sa.text("100"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(action_text) <= 1000",
            name=op.f("ck_action_library_action_text_max_length"),
        ),
        sa.CheckConstraint(
            "char_length(completion_criteria) <= 1000",
            name=op.f("ck_action_library_completion_criteria_max_length"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(recommended_evidence) = 'array' "
            "AND jsonb_array_length(recommended_evidence) <= 5",
            name=op.f("ck_action_library_recommended_evidence_array"),
        ),
        sa.ForeignKeyConstraint(
            ["core_value_id"],
            ["core_values.id"],
            name="fk_action_library_core_value_id_core_values",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_action_library"),
        sa.UniqueConstraint("library_key", name="uq_action_library_library_key"),
    )
    op.create_index(
        "ix_action_library_core_value_id_is_active_priority",
        "action_library",
        ["core_value_id", "is_active", "priority"],
    )

    op.create_table(
        "assigned_actions",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", action_source_kind, nullable=False),
        sa.Column("source_action_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_text_snapshot", sa.Text(), nullable=False),
        sa.Column("completion_criteria_snapshot", sa.Text(), nullable=False),
        sa.Column(
            "recommended_evidence_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("display_order", sa.SmallInteger(), nullable=False),
        sa.Column("status", action_status, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(action_text_snapshot) <= 1000",
            name=op.f("ck_assigned_actions_action_text_max_length"),
        ),
        sa.CheckConstraint(
            "char_length(completion_criteria_snapshot) <= 1000",
            name=op.f("ck_assigned_actions_completion_criteria_max_length"),
        ),
        sa.CheckConstraint(
            "source_kind <> 'custom' OR created_by_user_id IS NOT NULL",
            name=op.f("ck_assigned_actions_custom_creator_required"),
        ),
        sa.CheckConstraint(
            "source_kind <> 'library' OR source_action_id IS NOT NULL",
            name=op.f("ck_assigned_actions_library_source_required"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(recommended_evidence_snapshot) = 'array'",
            name=op.f("ck_assigned_actions_recommended_evidence_array"),
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status = 'pending' AND completed_at IS NULL)",
            name=op.f("ck_assigned_actions_status_completed_at_match"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_assigned_actions_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["work_assignments.id"],
            name="fk_assigned_actions_assignment_id_work_assignments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_assigned_actions_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_action_id"],
            ["action_library.id"],
            name="fk_assigned_actions_source_action_id_action_library",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assigned_actions"),
    )
    op.create_index(
        "ix_assigned_actions_assignment_id_status",
        "assigned_actions",
        ["assignment_id", "status"],
    )
    op.create_index(
        "ix_assigned_actions_created_by_user_id", "assigned_actions", ["created_by_user_id"]
    )
    op.create_index(
        "ix_assigned_actions_source_action_id", "assigned_actions", ["source_action_id"]
    )
    op.create_index(
        "uq_assigned_actions_assignment_id_display_order",
        "assigned_actions",
        ["assignment_id", "display_order"],
        unique=True,
    )
    op.create_index(
        "uq_assigned_actions_assignment_id_source_action_id_library",
        "assigned_actions",
        ["assignment_id", "source_action_id"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'library'"),
    )

    op.create_table(
        "evidence_submissions",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("performed_action", sa.Text(), nullable=False),
        sa.Column("discovery", sa.Text(), nullable=False),
        sa.Column("changed_judgment", sa.Text(), nullable=False),
        sa.Column("work_impact", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(changed_judgment) BETWEEN 10 AND 2000",
            name=op.f("ck_evidence_submissions_changed_judgment_length"),
        ),
        sa.CheckConstraint(
            "char_length(discovery) BETWEEN 10 AND 2000",
            name=op.f("ck_evidence_submissions_discovery_length"),
        ),
        sa.CheckConstraint(
            "char_length(next_action) BETWEEN 10 AND 1000",
            name=op.f("ck_evidence_submissions_next_action_length"),
        ),
        sa.CheckConstraint(
            "char_length(performed_action) BETWEEN 10 AND 2000",
            name=op.f("ck_evidence_submissions_performed_action_length"),
        ),
        sa.CheckConstraint(
            "char_length(work_impact) BETWEEN 10 AND 2000",
            name=op.f("ck_evidence_submissions_work_impact_length"),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["work_assignments.id"],
            name="fk_evidence_submissions_assignment_id_work_assignments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["users.id"],
            name="fk_evidence_submissions_employee_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_submissions"),
        sa.UniqueConstraint("assignment_id", name="uq_evidence_submissions_assignment_id"),
    )
    op.create_index(
        "ix_evidence_submissions_employee_id", "evidence_submissions", ["employee_id"]
    )

    op.create_table(
        "evidence_submission_actions",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assigned_action_id"],
            ["assigned_actions.id"],
            name="fk_evidence_submission_actions_action",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence_submissions.id"],
            name="fk_evidence_submission_actions_evidence",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "evidence_id", "assigned_action_id", name="pk_evidence_submission_actions"
        ),
    )
    op.create_index(
        "ix_evidence_submission_actions_assigned_action_id",
        "evidence_submission_actions",
        ["assigned_action_id"],
    )

    op.create_table(
        "evidence_links",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence_submissions.id"],
            name="fk_evidence_links_evidence_id_evidence_submissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_links"),
    )
    op.create_index("ix_evidence_links_evidence_id", "evidence_links", ["evidence_id"])

    op.create_table(
        "evidence_cards",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", evidence_card_status, nullable=False),
        sa.Column(
            "generated_content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("final_content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_by", ai_provider, nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("schema_version", sa.String(length=30), nullable=False),
        sa.Column(
            "generation_attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("generation_latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_error_code", sa.String(length=50), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manager_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "generation_attempts >= 0",
            name=op.f("ck_evidence_cards_generation_attempts_nonnegative"),
        ),
        sa.CheckConstraint(
            "generation_latency_ms IS NULL OR generation_latency_ms >= 0",
            name=op.f("ck_evidence_cards_generation_latency_nonnegative"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_evidence_cards_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence_submissions.id"],
            name="fk_evidence_cards_evidence_id_evidence_submissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_cards"),
        sa.UniqueConstraint("evidence_id", name="uq_evidence_cards_evidence_id"),
    )
    op.create_index(
        "ix_evidence_cards_status_updated_at", "evidence_cards", ["status", "updated_at"]
    )

    op.create_table(
        "manager_feedbacks",
        sa.Column("evidence_card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_behavior", sa.Text(), nullable=False),
        sa.Column("work_impact", sa.Text(), nullable=False),
        sa.Column("positive_feedback", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(next_action) BETWEEN 10 AND 1000",
            name=op.f("ck_manager_feedbacks_next_action_length"),
        ),
        sa.CheckConstraint(
            "char_length(observed_behavior) BETWEEN 10 AND 1000",
            name=op.f("ck_manager_feedbacks_observed_behavior_length"),
        ),
        sa.CheckConstraint(
            "char_length(positive_feedback) BETWEEN 10 AND 1000",
            name=op.f("ck_manager_feedbacks_positive_feedback_length"),
        ),
        sa.CheckConstraint(
            "char_length(work_impact) BETWEEN 10 AND 1000",
            name=op.f("ck_manager_feedbacks_work_impact_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_card_id"],
            ["evidence_cards.id"],
            name="fk_manager_feedbacks_evidence_card_id_evidence_cards",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["manager_id"],
            ["users.id"],
            name="fk_manager_feedbacks_manager_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_manager_feedbacks"),
        sa.UniqueConstraint("evidence_card_id", name="uq_manager_feedbacks_evidence_card_id"),
    )
    op.create_index(
        "ix_manager_feedbacks_manager_id_submitted_at",
        "manager_feedbacks",
        ["manager_id", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_manager_feedbacks_manager_id_submitted_at", table_name="manager_feedbacks")
    op.drop_table("manager_feedbacks")
    op.drop_index("ix_evidence_cards_status_updated_at", table_name="evidence_cards")
    op.drop_table("evidence_cards")
    op.drop_index("ix_evidence_links_evidence_id", table_name="evidence_links")
    op.drop_table("evidence_links")
    op.drop_index(
        "ix_evidence_submission_actions_assigned_action_id",
        table_name="evidence_submission_actions",
    )
    op.drop_table("evidence_submission_actions")
    op.drop_index("ix_evidence_submissions_employee_id", table_name="evidence_submissions")
    op.drop_table("evidence_submissions")
    op.drop_index(
        "uq_assigned_actions_assignment_id_source_action_id_library",
        table_name="assigned_actions",
    )
    op.drop_index(
        "uq_assigned_actions_assignment_id_display_order", table_name="assigned_actions"
    )
    op.drop_index("ix_assigned_actions_source_action_id", table_name="assigned_actions")
    op.drop_index("ix_assigned_actions_created_by_user_id", table_name="assigned_actions")
    op.drop_index("ix_assigned_actions_assignment_id_status", table_name="assigned_actions")
    op.drop_table("assigned_actions")
    op.drop_index(
        "ix_action_library_core_value_id_is_active_priority", table_name="action_library"
    )
    op.drop_table("action_library")
    op.drop_index("ix_work_assignments_manager_id_status", table_name="work_assignments")
    op.drop_index("ix_work_assignments_employee_id_status", table_name="work_assignments")
    op.drop_table("work_assignments")
    op.drop_index(
        "uq_onboarding_weeks_profile_id_week_number", table_name="onboarding_weeks"
    )
    op.drop_index("ix_onboarding_weeks_curriculum_week_id", table_name="onboarding_weeks")
    op.drop_index("ix_onboarding_weeks_core_value_id", table_name="onboarding_weeks")
    op.drop_table("onboarding_weeks")
    op.drop_table("curriculum_weeks")
    op.drop_index("ix_onboarding_profiles_manager_id", table_name="onboarding_profiles")
    op.drop_table("onboarding_profiles")
    op.drop_table("core_values")
    op.drop_index("ix_auth_sessions_user_id_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_auth_rate_limits_blocked_until", table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_type in reversed(enum_types):
        enum_type.drop(bind, checkfirst=False)
