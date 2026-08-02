from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.schema import Table

from app.core.config import Settings
from app.models import (
    ActionLibrary,
    AssignedAction,
    AuthSession,
    CoreValue,
    CurriculumWeek,
    EvidenceSubmission,
    EvidenceSubmissionAction,
    OnboardingProfile,
    OnboardingWeek,
    User,
    WorkAssignment,
)
from app.models.enums import (
    ActionSourceKind,
    ActionStatus,
    AssignmentStatus,
    OnboardingStage,
    UserRole,
    WorkType,
)
from app.security.passwords import get_password_manager

DEMO_EMPLOYEE_KEY = "demo.employee"
DEMO_MANAGER_KEY = "demo.manager"
DEMO_HR_KEY = "demo.hr"
DEMO_USER_KEYS = (DEMO_EMPLOYEE_KEY, DEMO_MANAGER_KEY, DEMO_HR_KEY)
DEMO_ASSIGNMENT_SEED_KEY = "demo.week2.hr_inquiry_prototype"


@dataclass(frozen=True)
class CoreValueFixture:
    code: str
    name: str
    short_description: str


@dataclass(frozen=True)
class ActionFixture:
    library_key: str
    action_text: str
    completion_criteria: str
    recommended_evidence: tuple[str, ...]
    priority: int
    initial_status: ActionStatus


CORE_VALUE_FIXTURES = (
    CoreValueFixture(
        "relationship_based_strategic_communication",
        "관계기반 전략소통",
        "관계와 맥락을 이해하고 목적에 맞게 소통합니다.",
    ),
    CoreValueFixture(
        "obsessive_curiosity",
        "강박적 호기심",
        "질문과 검증으로 문제의 본질을 탐색합니다.",
    ),
    CoreValueFixture(
        "growth_oriented_feedback",
        "성장지향 피드백",
        "구체적인 피드백을 주고받아 다음 행동을 개선합니다.",
    ),
    CoreValueFixture(
        "value_centered_problem_solving",
        "가치중심적 문제해결",
        "사용자와 조직의 가치를 기준으로 문제를 해결합니다.",
    ),
    CoreValueFixture(
        "fundamental_critical_thinking",
        "근본적 비판 사고",
        "전제를 점검하고 근본 원인을 비판적으로 검토합니다.",
    ),
    CoreValueFixture(
        "leading_quantitative_goal_orientation",
        "선도적/정량 목표의식",
        "측정 가능한 목표를 세우고 선제적으로 실행합니다.",
    ),
    CoreValueFixture(
        "ultra_efficient_time_management",
        "초효율적 시간관리",
        "중요한 일에 시간을 집중하고 낭비를 줄입니다.",
    ),
    CoreValueFixture(
        "innovation_process_acceleration",
        "혁신 프로세스 가속화",
        "새로운 도구와 방법으로 실행 과정을 빠르게 개선합니다.",
    ),
    CoreValueFixture(
        "persistent_perseverance",
        "집요한 끈기",
        "실패 원인을 학습하며 해결될 때까지 시도합니다.",
    ),
    CoreValueFixture(
        "highest_standard_results",
        "최고수준의 결과지향",
        "명확한 완료 기준으로 결과물의 완성도를 높입니다.",
    ),
    CoreValueFixture(
        "self_driven_growth_motivation",
        "자발적 성장동기",
        "스스로 성장 목표를 정하고 학습을 실행합니다.",
    ),
    CoreValueFixture(
        "future_optimistic_challenge",
        "미래낙관적 도전",
        "불확실성 속에서도 가능성을 보고 새로운 시도를 시작합니다.",
    ),
)

ACTION_FIXTURES = (
    ActionFixture(
        "demo.obsessive_curiosity.hypothesis",
        "구현 전에 문제의 근본 원인에 대한 가설을 한 문장으로 작성한다.",
        "검증 가능한 가설이 한 문장으로 기록되어 있다.",
        ("문제 가설 문서",),
        10,
        ActionStatus.COMPLETED,
    ),
    ActionFixture(
        "demo.obsessive_curiosity.interview",
        "실제 사용자 또는 업무 담당자 2명 이상에게 현재 업무 흐름을 확인한다.",
        "2명 이상의 인터뷰 또는 확인 기록이 있다.",
        ("사용자 인터뷰 기록", "As-Is 업무 흐름도"),
        20,
        ActionStatus.COMPLETED,
    ),
    ActionFixture(
        "demo.obsessive_curiosity.judgment_change",
        "처음 가설과 조사 후 판단이 어떻게 달라졌는지 기록한다.",
        "조사 전후의 판단 변화가 한 문장 이상 기록되어 있다.",
        ("변경된 기능 정의서",),
        30,
        ActionStatus.PENDING,
    ),
)


def stage_for_week(week_number: int) -> OnboardingStage:
    if week_number <= 4:
        return OnboardingStage.GUIDED
    if week_number <= 8:
        return OnboardingStage.ASSISTED
    return OnboardingStage.AUTONOMOUS


async def _upsert_id(
    session: AsyncSession,
    table: Table,
    *,
    values: dict[str, Any],
    conflict_columns: tuple[str, ...],
    update_columns: tuple[str, ...],
) -> UUID:
    statement = postgresql_insert(table).values(id=uuid4(), **values)
    updates = {column: getattr(statement.excluded, column) for column in update_columns}
    if "updated_at" in table.c:
        updates["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(
        index_elements=[table.c[column] for column in conflict_columns],
        set_=updates,
    ).returning(table.c.id)
    return (await session.execute(statement)).scalar_one()


async def seed_demo_data(session: AsyncSession, settings: Settings) -> None:
    """Upsert the fictional Phase 1 fixture without committing the caller's transaction."""

    password_hash = get_password_manager().hash(
        settings.demo_account_password.get_secret_value()
    )
    user_specs = (
        (
            DEMO_EMPLOYEE_KEY,
            "김가온",
            "employee@ix-demo.test",
            UserRole.EMPLOYEE,
        ),
        (
            DEMO_MANAGER_KEY,
            "박도윤",
            "manager@ix-demo.test",
            UserRole.MANAGER,
        ),
        (
            DEMO_HR_KEY,
            "이서윤",
            "hr@ix-demo.test",
            UserRole.HR,
        ),
    )
    user_ids: dict[str, UUID] = {}
    for fixture_key, name, email, role in user_specs:
        user_ids[fixture_key] = await _upsert_id(
            session,
            User.__table__,
            values={
                "name": name,
                "email": email,
                "normalized_email": email,
                "password_hash": password_hash,
                "role": role,
                "is_active": True,
                "demo_fixture_key": fixture_key,
            },
            conflict_columns=("demo_fixture_key",),
            update_columns=(
                "name",
                "email",
                "normalized_email",
                "password_hash",
                "role",
                "is_active",
            ),
        )

    core_value_ids: dict[str, UUID] = {}
    for display_order, fixture in enumerate(CORE_VALUE_FIXTURES, start=1):
        full_description = (
            f"{fixture.short_description} 실제 업무의 행동과 근거로 확인하는 데모 정의입니다."
        )
        core_value_ids[fixture.code] = await _upsert_id(
            session,
            CoreValue.__table__,
            values={
                "code": fixture.code,
                "name": fixture.name,
                "short_description": fixture.short_description,
                "full_description": full_description,
                "display_order": display_order,
                "is_active": True,
            },
            conflict_columns=("code",),
            update_columns=(
                "name",
                "short_description",
                "full_description",
                "display_order",
                "is_active",
            ),
        )

    curriculum_ids: dict[int, UUID] = {}
    for week_number, fixture in enumerate(CORE_VALUE_FIXTURES, start=1):
        curriculum_ids[week_number] = await _upsert_id(
            session,
            CurriculumWeek.__table__,
            values={
                "week_number": week_number,
                "core_value_id": core_value_ids[fixture.code],
                "stage": stage_for_week(week_number),
            },
            conflict_columns=("week_number",),
            update_columns=("core_value_id", "stage"),
        )

    profile_start_date = settings.demo_reference_date - timedelta(days=13)
    profile_id = await _upsert_id(
        session,
        OnboardingProfile.__table__,
        values={
            "user_id": user_ids[DEMO_EMPLOYEE_KEY],
            "job_role": "ax",
            "start_date": profile_start_date,
            "manager_id": user_ids[DEMO_MANAGER_KEY],
            "demo_week_override": 2,
        },
        conflict_columns=("user_id",),
        update_columns=(
            "job_role",
            "start_date",
            "manager_id",
            "demo_week_override",
        ),
    )

    onboarding_week_ids: dict[int, UUID] = {}
    for week_number, fixture in enumerate(CORE_VALUE_FIXTURES, start=1):
        starts_on = profile_start_date + timedelta(days=(week_number - 1) * 7)
        onboarding_week_ids[week_number] = await _upsert_id(
            session,
            OnboardingWeek.__table__,
            values={
                "profile_id": profile_id,
                "week_number": week_number,
                "curriculum_week_id": curriculum_ids[week_number],
                "core_value_id": core_value_ids[fixture.code],
                "stage": stage_for_week(week_number),
                "starts_on": starts_on,
                "ends_on": starts_on + timedelta(days=6),
            },
            conflict_columns=("profile_id", "week_number"),
            update_columns=(
                "curriculum_week_id",
                "core_value_id",
                "stage",
                "starts_on",
                "ends_on",
            ),
        )

    action_library_ids: dict[str, UUID] = {}
    for fixture in ACTION_FIXTURES:
        action_library_ids[fixture.library_key] = await _upsert_id(
            session,
            ActionLibrary.__table__,
            values={
                "library_key": fixture.library_key,
                "core_value_id": core_value_ids["obsessive_curiosity"],
                "job_role": "ax",
                "work_type": WorkType.PROTOTYPE_BUILD,
                "onboarding_stage": OnboardingStage.GUIDED,
                "action_text": fixture.action_text,
                "recommended_evidence": list(fixture.recommended_evidence),
                "completion_criteria": fixture.completion_criteria,
                "priority": fixture.priority,
                "is_active": True,
            },
            conflict_columns=("library_key",),
            update_columns=(
                "core_value_id",
                "job_role",
                "work_type",
                "onboarding_stage",
                "action_text",
                "recommended_evidence",
                "completion_criteria",
                "priority",
                "is_active",
            ),
        )

    assignment_id = await _upsert_id(
        session,
        WorkAssignment.__table__,
        values={
            "onboarding_week_id": onboarding_week_ids[2],
            "employee_id": user_ids[DEMO_EMPLOYEE_KEY],
            "manager_id": user_ids[DEMO_MANAGER_KEY],
            "title": "반복적인 HR 문의 분석 및 자동화 프로토타입 구축",
            "description": (
                "반복 문의의 원인을 확인하고 사용자가 쉽게 접근할 수 있는 "
                "단일 문의 진입점 프로토타입을 만든다."
            ),
            "work_type": WorkType.PROTOTYPE_BUILD,
            "start_date": profile_start_date + timedelta(days=7),
            "due_date": profile_start_date + timedelta(days=13),
            "status": AssignmentStatus.ACTIVE,
            "seed_key": DEMO_ASSIGNMENT_SEED_KEY,
        },
        conflict_columns=("seed_key",),
        update_columns=(
            "onboarding_week_id",
            "employee_id",
            "manager_id",
            "title",
            "description",
            "work_type",
            "start_date",
            "due_date",
            "status",
        ),
    )

    completed_at = datetime.combine(
        settings.demo_reference_date - timedelta(days=2),
        time(hour=4),
        tzinfo=UTC,
    )
    for display_order, fixture in enumerate(ACTION_FIXTURES, start=1):
        await _upsert_id(
            session,
            AssignedAction.__table__,
            values={
                "assignment_id": assignment_id,
                "source_kind": ActionSourceKind.LIBRARY,
                "source_action_id": action_library_ids[fixture.library_key],
                "created_by_user_id": None,
                "action_text_snapshot": fixture.action_text,
                "completion_criteria_snapshot": fixture.completion_criteria,
                "recommended_evidence_snapshot": list(fixture.recommended_evidence),
                "is_required": True,
                "display_order": display_order,
                "status": fixture.initial_status,
                "completed_at": (
                    completed_at if fixture.initial_status is ActionStatus.COMPLETED else None
                ),
                "version": 1,
            },
            conflict_columns=("assignment_id", "display_order"),
            update_columns=(
                "source_kind",
                "source_action_id",
                "created_by_user_id",
                "action_text_snapshot",
                "completion_criteria_snapshot",
                "recommended_evidence_snapshot",
                "is_required",
                "status",
                "completed_at",
                "version",
            ),
        )


async def reset_demo_data(session: AsyncSession, settings: Settings) -> None:
    """Reset only allowlisted demo progress and reseed it in the caller's transaction."""

    if settings.app_env not in {"demo", "test"}:
        raise RuntimeError("Demo reset is allowed only when APP_ENV is demo or test")

    demo_user_ids = select(User.id).where(User.demo_fixture_key.in_(DEMO_USER_KEYS))
    assignment_ids = select(WorkAssignment.id).where(
        WorkAssignment.seed_key == DEMO_ASSIGNMENT_SEED_KEY
    )
    evidence_ids = select(EvidenceSubmission.id).where(
        EvidenceSubmission.assignment_id.in_(assignment_ids)
    )

    await session.execute(
        delete(EvidenceSubmissionAction).where(
            EvidenceSubmissionAction.evidence_id.in_(evidence_ids)
        )
    )
    await session.execute(
        delete(WorkAssignment).where(WorkAssignment.seed_key == DEMO_ASSIGNMENT_SEED_KEY)
    )
    await session.execute(
        delete(OnboardingProfile).where(
            OnboardingProfile.user_id
            == select(User.id)
            .where(User.demo_fixture_key == DEMO_EMPLOYEE_KEY)
            .scalar_subquery()
        )
    )
    await session.execute(delete(AuthSession).where(AuthSession.user_id.in_(demo_user_ids)))

    await seed_demo_data(session, settings)
