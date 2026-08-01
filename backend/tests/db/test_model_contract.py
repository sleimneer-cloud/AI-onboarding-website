from unittest.mock import AsyncMock

import pytest
from sqlalchemy import DateTime, Enum, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID

import app.models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base
from app.models.enums import (
    ActionSourceKind,
    ActionStatus,
    AIProvider,
    AssignmentStatus,
    EvidenceCardStatus,
    OnboardingStage,
    UserRole,
    WorkType,
)
from app.services.demo_data import (
    ACTION_FIXTURES,
    CORE_VALUE_FIXTURES,
    reset_demo_data,
    stage_for_week,
)

EXPECTED_TABLES = {
    "users",
    "auth_sessions",
    "auth_rate_limits",
    "onboarding_profiles",
    "core_values",
    "curriculum_weeks",
    "onboarding_weeks",
    "work_assignments",
    "action_library",
    "assigned_actions",
    "evidence_submissions",
    "evidence_submission_actions",
    "evidence_links",
    "evidence_cards",
    "manager_feedbacks",
}

EXPECTED_ENUMS = {
    "user_role": [member.value for member in UserRole],
    "onboarding_stage": [member.value for member in OnboardingStage],
    "work_type": [member.value for member in WorkType],
    "assignment_status": [member.value for member in AssignmentStatus],
    "action_source_kind": [member.value for member in ActionSourceKind],
    "action_status": [member.value for member in ActionStatus],
    "evidence_card_status": [member.value for member in EvidenceCardStatus],
    "ai_provider": [member.value for member in AIProvider],
}

EXPECTED_COLUMNS = {
    "users": {
        "id", "name", "email", "normalized_email", "password_hash", "role",
        "is_active", "demo_fixture_key", "created_at", "updated_at",
    },
    "auth_sessions": {
        "id", "user_id", "token_hash", "csrf_token_hash", "expires_at", "revoked_at",
        "last_seen_at", "created_at",
    },
    "auth_rate_limits": {
        "id", "subject_hash", "window_started_at", "failure_count", "blocked_until",
        "updated_at",
    },
    "onboarding_profiles": {
        "id", "user_id", "job_role", "start_date", "manager_id", "demo_week_override",
        "created_at", "updated_at",
    },
    "core_values": {
        "id", "code", "name", "short_description", "full_description", "display_order",
        "is_active", "created_at", "updated_at",
    },
    "curriculum_weeks": {
        "id", "week_number", "core_value_id", "stage", "created_at", "updated_at",
    },
    "onboarding_weeks": {
        "id", "profile_id", "week_number", "curriculum_week_id", "core_value_id", "stage",
        "starts_on", "ends_on", "created_at",
    },
    "work_assignments": {
        "id", "onboarding_week_id", "employee_id", "manager_id", "title", "description",
        "work_type", "start_date", "due_date", "status", "seed_key", "created_at",
        "updated_at",
    },
    "action_library": {
        "id", "library_key", "core_value_id", "job_role", "work_type", "onboarding_stage",
        "action_text", "recommended_evidence", "completion_criteria", "priority", "is_active",
        "created_at", "updated_at",
    },
    "assigned_actions": {
        "id", "assignment_id", "source_kind", "source_action_id", "created_by_user_id",
        "action_text_snapshot", "completion_criteria_snapshot", "recommended_evidence_snapshot",
        "is_required", "display_order", "status", "completed_at", "created_at", "updated_at",
        "version",
    },
    "evidence_submissions": {
        "id", "assignment_id", "employee_id", "performed_action", "discovery",
        "changed_judgment", "work_impact", "next_action", "submitted_at", "created_at",
    },
    "evidence_submission_actions": {"evidence_id", "assigned_action_id"},
    "evidence_links": {"id", "evidence_id", "external_url", "title", "description", "created_at"},
    "evidence_cards": {
        "id", "evidence_id", "status", "generated_content_json", "final_content_json",
        "generated_by", "model_name", "prompt_version", "schema_version",
        "generation_attempts", "generation_latency_ms", "last_error_code", "confirmed_at",
        "manager_reviewed_at", "created_at", "updated_at", "version",
    },
    "manager_feedbacks": {
        "id", "evidence_card_id", "manager_id", "observed_behavior", "work_impact",
        "positive_feedback", "next_action", "submitted_at", "created_at",
    },
}


def test_metadata_contains_exact_phase_one_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_table_columns_and_postgresql_types_match_contract() -> None:
    assert {
        name: set(table.columns.keys()) for name, table in Base.metadata.tables.items()
    } == EXPECTED_COLUMNS

    for table in Base.metadata.tables.values():
        for primary_key_column in table.primary_key.columns:
            assert isinstance(primary_key_column.type, UUID)
        for column in table.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True

    assert isinstance(Base.metadata.tables["action_library"].c.recommended_evidence.type, JSONB)
    assert isinstance(
        Base.metadata.tables["assigned_actions"].c.recommended_evidence_snapshot.type,
        JSONB,
    )
    assert isinstance(Base.metadata.tables["evidence_cards"].c.generated_content_json.type, JSONB)
    assert isinstance(Base.metadata.tables["evidence_cards"].c.final_content_json.type, JSONB)
    assert {
        table.name for table in Base.metadata.tables.values() if "version" in table.c
    } == {"assigned_actions", "evidence_cards"}


def test_native_enum_names_and_values_match_contract() -> None:
    actual: dict[str, list[str]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, Enum) and column.type.native_enum:
                actual[column.type.name] = list(column.type.enums)

    assert actual == EXPECTED_ENUMS


def test_required_indexes_exist_with_column_order_and_partial_predicate() -> None:
    expected = {
        "ix_auth_sessions_user_id_expires_at": ("user_id", "expires_at"),
        "ix_auth_rate_limits_blocked_until": ("blocked_until",),
        "ix_onboarding_profiles_manager_id": ("manager_id",),
        "uq_onboarding_weeks_profile_id_week_number": ("profile_id", "week_number"),
        "ix_work_assignments_employee_id_status": ("employee_id", "status"),
        "ix_work_assignments_manager_id_status": ("manager_id", "status"),
        "ix_assigned_actions_assignment_id_status": ("assignment_id", "status"),
        "ix_evidence_cards_status_updated_at": ("status", "updated_at"),
        "ix_manager_feedbacks_manager_id_submitted_at": ("manager_id", "submitted_at"),
        "ix_action_library_core_value_id_is_active_priority": (
            "core_value_id",
            "is_active",
            "priority",
        ),
    }
    indexes: dict[str, Index] = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if index.name is not None
    }

    for name, columns in expected.items():
        assert tuple(column.name for column in indexes[name].columns) == columns

    partial = indexes["uq_assigned_actions_assignment_id_source_action_id_library"]
    assert partial.unique is True
    assert str(partial.dialect_options["postgresql"]["where"]) == "source_kind = 'library'"


def test_foreign_key_delete_policies_match_contract() -> None:
    expected = {
        ("auth_sessions", "user_id"): "CASCADE",
        ("onboarding_profiles", "user_id"): "CASCADE",
        ("onboarding_profiles", "manager_id"): "RESTRICT",
        ("onboarding_weeks", "profile_id"): "CASCADE",
        ("onboarding_weeks", "curriculum_week_id"): "RESTRICT",
        ("onboarding_weeks", "core_value_id"): "RESTRICT",
        ("work_assignments", "onboarding_week_id"): "CASCADE",
        ("work_assignments", "employee_id"): "RESTRICT",
        ("work_assignments", "manager_id"): "RESTRICT",
        ("assigned_actions", "assignment_id"): "CASCADE",
        ("assigned_actions", "source_action_id"): "RESTRICT",
        ("assigned_actions", "created_by_user_id"): "RESTRICT",
        ("evidence_submissions", "assignment_id"): "CASCADE",
        ("evidence_submissions", "employee_id"): "RESTRICT",
        ("evidence_submission_actions", "evidence_id"): "CASCADE",
        ("evidence_submission_actions", "assigned_action_id"): "RESTRICT",
        ("evidence_links", "evidence_id"): "CASCADE",
        ("evidence_cards", "evidence_id"): "CASCADE",
        ("manager_feedbacks", "evidence_card_id"): "CASCADE",
        ("manager_feedbacks", "manager_id"): "RESTRICT",
    }

    actual = {}
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            actual[(table.name, foreign_key.parent.name)] = foreign_key.ondelete

    assert actual.items() >= expected.items()


def test_fixture_catalog_is_complete_and_has_expected_initial_state() -> None:
    assert len(CORE_VALUE_FIXTURES) == 12
    assert len({fixture.code for fixture in CORE_VALUE_FIXTURES}) == 12
    assert len(ACTION_FIXTURES) == 3
    assert sum(action.initial_status is ActionStatus.COMPLETED for action in ACTION_FIXTURES) == 2
    assert [stage_for_week(week) for week in range(1, 13)] == [
        *([OnboardingStage.GUIDED] * 4),
        *([OnboardingStage.ASSISTED] * 4),
        *([OnboardingStage.AUTONOMOUS] * 4),
    ]


async def test_reset_rejects_non_demo_environment_before_database_access() -> None:
    session = AsyncMock()
    settings = Settings(_env_file=None, app_env="local")

    with pytest.raises(RuntimeError, match="APP_ENV"):
        await reset_demo_data(session, settings)

    session.execute.assert_not_awaited()
