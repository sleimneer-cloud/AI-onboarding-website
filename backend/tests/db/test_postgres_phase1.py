from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.config import Config
from argon2 import PasswordHasher
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import REPOSITORY_ROOT, Settings
from app.db.session import create_database_engine, create_session_factory, transaction
from app.main import create_app
from app.models import AssignedAction, EvidenceSubmission, User, WorkAssignment
from app.models.enums import ActionSourceKind, ActionStatus, UserRole
from app.services.demo_data import (
    DEMO_ASSIGNMENT_SEED_KEY,
    DEMO_USER_KEYS,
    reset_demo_data,
    seed_demo_data,
)
from app.services.readiness import check_database_ready

pytestmark = pytest.mark.postgres

DOMAIN_TABLES = {
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

ENUM_NAMES = {
    "user_role",
    "onboarding_stage",
    "work_type",
    "assignment_status",
    "action_source_kind",
    "action_status",
    "evidence_card_status",
    "ai_provider",
}


def alembic_config() -> Config:
    return Config(str(REPOSITORY_ROOT / "backend" / "alembic.ini"))


def enum_names(connection) -> set[str]:
    rows = connection.execute(
        text(
            "SELECT typname FROM pg_type "
            "WHERE typtype = 'e' AND typname = ANY(:enum_names)"
        ),
        {"enum_names": list(ENUM_NAMES)},
    )
    return set(rows.scalars())


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(database_url)
    if not parsed_url.drivername.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if "test" not in (parsed_url.database or "").lower():
        pytest.fail("Refusing destructive migration tests outside a database named with 'test'")

    sync_engine = create_engine(database_url, pool_pre_ping=True)
    with sync_engine.connect() as connection:
        server_version = int(connection.scalar(text("SHOW server_version_num")))
    sync_engine.dispose()
    if server_version < 160000:
        pytest.fail("Phase 1 requires PostgreSQL 16 or newer")

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    config = alembic_config()
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        yield database_url
    finally:
        command.downgrade(config, "base")
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


def test_migration_round_trip_and_postgresql_types(postgres_url: str) -> None:
    config = alembic_config()
    sync_engine = create_engine(postgres_url)
    try:
        with sync_engine.connect() as connection:
            assert DOMAIN_TABLES <= set(inspect(connection).get_table_names())
            assert enum_names(connection) == ENUM_NAMES

        command.downgrade(config, "base")
        with sync_engine.connect() as connection:
            assert DOMAIN_TABLES.isdisjoint(inspect(connection).get_table_names())
            assert enum_names(connection) == set()

        command.upgrade(config, "head")
        with sync_engine.connect() as connection:
            assert DOMAIN_TABLES <= set(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20260802_0001"
            )
    finally:
        sync_engine.dispose()


def test_migration_matches_model_metadata(postgres_url: str) -> None:
    del postgres_url
    command.check(alembic_config())


def test_migration_does_not_disable_application_loggers(postgres_url: str) -> None:
    del postgres_url
    application_logger = logging.getLogger("app.core.exception_handlers")
    application_logger.disabled = False

    command.check(alembic_config())

    assert application_logger.disabled is False


def test_actual_schema_indexes_and_delete_policies(postgres_url: str) -> None:
    sync_engine = create_engine(postgres_url)
    try:
        inspector = inspect(sync_engine)
        assigned_indexes = {
            index["name"]: index for index in inspector.get_indexes("assigned_actions")
        }
        partial = assigned_indexes[
            "uq_assigned_actions_assignment_id_source_action_id_library"
        ]
        assert partial["unique"] is True
        assert "source_kind" in str(partial["dialect_options"]["postgresql_where"])

        foreign_keys = {
            (table, constrained_column): foreign_key["options"].get("ondelete")
            for table in DOMAIN_TABLES
            for foreign_key in inspector.get_foreign_keys(table)
            for constrained_column in foreign_key["constrained_columns"]
        }
        assert foreign_keys[("auth_sessions", "user_id")] == "CASCADE"
        assert foreign_keys[("onboarding_profiles", "manager_id")] == "RESTRICT"
        assert foreign_keys[("work_assignments", "onboarding_week_id")] == "CASCADE"
        assert foreign_keys[("manager_feedbacks", "manager_id")] == "RESTRICT"
    finally:
        sync_engine.dispose()


async def test_seed_is_idempotent_and_reset_preserves_non_demo_rows(postgres_url: str) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=postgres_url,
        demo_account_password="TestDemoPassword!",
    )
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    sentinel_id = uuid4()
    try:
        async with transaction(session_factory) as session:
            await seed_demo_data(session, settings)

        async with transaction(session_factory) as session:
            first_ids = dict(
                (
                    await session.execute(
                        select(User.demo_fixture_key, User.id).where(
                            User.demo_fixture_key.in_(DEMO_USER_KEYS)
                        )
                    )
                ).all()
            )
            await seed_demo_data(session, settings)

        async with transaction(session_factory) as session:
            second_ids = dict(
                (
                    await session.execute(
                        select(User.demo_fixture_key, User.id).where(
                            User.demo_fixture_key.in_(DEMO_USER_KEYS)
                        )
                    )
                ).all()
            )
            password_hashes = (
                await session.execute(
                    select(User.password_hash).where(User.demo_fixture_key.in_(DEMO_USER_KEYS))
                )
            ).scalars().all()
            assignment_id = await session.scalar(
                select(WorkAssignment.id).where(
                    WorkAssignment.seed_key == DEMO_ASSIGNMENT_SEED_KEY
                )
            )
            assert assignment_id is not None
            actions = (
                await session.execute(
                    select(AssignedAction.status).where(
                        AssignedAction.assignment_id == assignment_id
                    )
                )
            ).scalars().all()
            evidence_count = await session.scalar(
                select(text("count(*)")).select_from(EvidenceSubmission)
            )

            session.add(
                User(
                    id=sentinel_id,
                    name="비데모 사용자",
                    email="sentinel@example.test",
                    normalized_email="sentinel@example.test",
                    password_hash=PasswordHasher().hash("SentinelPassword!"),
                    role=UserRole.HR,
                    is_active=True,
                )
            )

        assert first_ids == second_ids
        assert len(second_ids) == 3
        assert all(password_hash.startswith("$argon2id$") for password_hash in password_hashes)
        assert actions.count(ActionStatus.COMPLETED) == 2
        assert actions.count(ActionStatus.PENDING) == 1
        assert evidence_count == 0

        async with transaction(session_factory) as session:
            await reset_demo_data(session, settings)

        async with transaction(session_factory) as session:
            assert await session.get(User, sentinel_id) is not None
            assert (
                await session.scalar(
                    select(text("count(*)"))
                    .select_from(User)
                    .where(User.demo_fixture_key.in_(DEMO_USER_KEYS))
                )
                == 3
            )
    finally:
        async with transaction(session_factory) as session:
            sentinel = await session.get(User, sentinel_id)
            if sentinel is not None:
                await session.delete(sentinel)
        await engine.dispose()


async def test_database_constraints_reject_duplicate_and_invalid_actions(
    postgres_url: str,
) -> None:
    settings = Settings(_env_file=None, app_env="test", database_url=postgres_url)
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with transaction(session_factory) as session:
            await reset_demo_data(session, settings)
            assignment = (
                await session.execute(
                    select(WorkAssignment).where(
                        WorkAssignment.seed_key == DEMO_ASSIGNMENT_SEED_KEY
                    )
                )
            ).scalar_one()
            assignment_id = assignment.id
            onboarding_week_id = assignment.onboarding_week_id
            employee_id = assignment.employee_id
            manager_id = assignment.manager_id

        with pytest.raises(IntegrityError) as duplicate_assignment:
            async with transaction(session_factory) as session:
                session.add(
                    WorkAssignment(
                        onboarding_week_id=onboarding_week_id,
                        employee_id=employee_id,
                        manager_id=manager_id,
                        title="중복 업무",
                        description="동일 주차의 두 번째 대표 업무를 차단하기 위한 테스트입니다.",
                        work_type=assignment.work_type,
                        start_date=assignment.start_date,
                        due_date=assignment.due_date,
                        seed_key="test.duplicate.assignment",
                    )
                )
        assert duplicate_assignment.value.orig.sqlstate == "23505"

        with pytest.raises(IntegrityError) as invalid_status:
            async with transaction(session_factory) as session:
                session.add(
                    AssignedAction(
                        assignment_id=assignment_id,
                        source_kind=ActionSourceKind.CUSTOM,
                        source_action_id=None,
                        created_by_user_id=manager_id,
                        action_text_snapshot="잘못된 상태 테스트",
                        completion_criteria_snapshot="완료 시각이 없어야 합니다.",
                        recommended_evidence_snapshot=[],
                        is_required=False,
                        display_order=99,
                        status=ActionStatus.PENDING,
                        completed_at=datetime.now(UTC),
                    )
                )
        assert invalid_status.value.orig.sqlstate == "23514"
    finally:
        await engine.dispose()


async def test_ready_uses_real_migrated_postgresql(postgres_url: str) -> None:
    settings = Settings(_env_file=None, app_env="test", database_url=postgres_url)
    assert await check_database_ready(settings) is True

    app = create_app(settings)
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
