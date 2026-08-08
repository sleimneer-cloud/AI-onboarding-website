from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ApiProblem
from app.db.session import transaction
from app.models.actions import AssignedAction, WorkAssignment
from app.models.enums import (
    ActionStatus,
    AssignmentStatus,
    EvidenceCardStatus,
)
from app.models.evidence import (
    EvidenceCard,
    EvidenceLink,
    EvidenceSubmission,
    EvidenceSubmissionAction,
)
from app.models.onboarding import CoreValue, OnboardingProfile, OnboardingWeek
from app.schemas.employee import (
    AssignedActionDetailResponse,
    AssignedActionResponse,
    AssignmentSummaryResponse,
    CoreValueSummaryResponse,
    DashboardEvidenceCardSummaryResponse,
    DashboardEvidenceSummaryResponse,
    EmployeeDashboardPermissionsResponse,
    EmployeeDashboardResponse,
    EmployeeOnboardingResponse,
    EvidenceCreateRequest,
    EvidenceLinkResponse,
    EvidenceResponse,
    ProgressResponse,
)

OverallStatus = Literal["not_started", "active", "completed"]
WeekStatus = Literal[
    "completed",
    "awaiting_manager",
    "reviewing_card",
    "generating_card",
    "generation_failed",
    "evidence_submitted",
    "in_progress",
    "ready",
    "not_configured",
    "locked",
]


def calculate_overall_status(start_date: date, reference_date: date) -> OverallStatus:
    elapsed_days = (reference_date - start_date).days
    if elapsed_days < 0:
        return "not_started"
    if elapsed_days >= 84:
        return "completed"
    return "active"


def calculate_week_number(profile: OnboardingProfile, reference_date: date) -> int:
    if profile.demo_week_override is not None:
        return profile.demo_week_override
    elapsed_days = (reference_date - profile.start_date).days
    return min(12, max(1, elapsed_days // 7 + 1))


def calculate_progress(actions: Sequence[AssignedAction]) -> ProgressResponse:
    total = len(actions)
    completed = sum(action.status is ActionStatus.COMPLETED for action in actions)
    percentage = 0 if total == 0 else int(completed * 100 / total + 0.5)
    return ProgressResponse(
        completed_actions=completed,
        total_actions=total,
        percentage=percentage,
    )


def derive_week_status(
    *,
    card_status: EvidenceCardStatus | None,
    evidence_exists: bool,
    completed_actions: int,
    assignment_exists: bool,
    future_week: bool,
) -> WeekStatus:
    card_statuses: dict[EvidenceCardStatus, WeekStatus] = {
        EvidenceCardStatus.MANAGER_REVIEWED: "completed",
        EvidenceCardStatus.USER_CONFIRMED: "awaiting_manager",
        EvidenceCardStatus.USER_REVIEW: "reviewing_card",
        EvidenceCardStatus.AI_PROCESSING: "generating_card",
        EvidenceCardStatus.GENERATION_FAILED: "generation_failed",
    }
    if card_status is not None:
        return card_statuses[card_status]
    if evidence_exists:
        return "evidence_submitted"
    if completed_actions > 0:
        return "in_progress"
    if assignment_exists:
        return "ready"
    if future_week:
        return "locked"
    return "not_configured"


class EmployeeService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        now: Callable[[], datetime] | None = None,
        reference_date: Callable[[], date] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._now = now or (lambda: datetime.now(UTC))
        self._reference_date = reference_date or self._default_reference_date

    async def get_dashboard(self, employee_id: UUID) -> EmployeeDashboardResponse:
        try:
            async with self._session_factory() as session:
                profile = (
                    await session.execute(
                        select(OnboardingProfile).where(
                            OnboardingProfile.user_id == employee_id
                        )
                    )
                ).scalar_one_or_none()
                if profile is None:
                    self._raise_resource_not_found()

                reference_date = self._reference_date()
                week_number = calculate_week_number(profile, reference_date)
                week_row = (
                    await session.execute(
                        select(OnboardingWeek, CoreValue)
                        .join(CoreValue, CoreValue.id == OnboardingWeek.core_value_id)
                        .where(
                            OnboardingWeek.profile_id == profile.id,
                            OnboardingWeek.week_number == week_number,
                        )
                    )
                ).one_or_none()
                if week_row is None:
                    self._raise_resource_not_found()
                onboarding_week, core_value = week_row

                assignment = (
                    await session.execute(
                        select(WorkAssignment).where(
                            WorkAssignment.onboarding_week_id == onboarding_week.id,
                            WorkAssignment.employee_id == employee_id,
                        )
                    )
                ).scalar_one_or_none()

                actions: list[AssignedAction] = []
                evidence: EvidenceSubmission | None = None
                card: EvidenceCard | None = None
                if assignment is not None:
                    actions = list(
                        (
                            await session.scalars(
                                select(AssignedAction)
                                .where(AssignedAction.assignment_id == assignment.id)
                                .order_by(AssignedAction.display_order)
                            )
                        ).all()
                    )
                    evidence = (
                        await session.execute(
                            select(EvidenceSubmission).where(
                                EvidenceSubmission.assignment_id == assignment.id,
                                EvidenceSubmission.employee_id == employee_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if evidence is not None:
                        card = (
                            await session.execute(
                                select(EvidenceCard).where(
                                    EvidenceCard.evidence_id == evidence.id
                                )
                            )
                        ).scalar_one_or_none()

                progress = calculate_progress(actions)
                week_status = derive_week_status(
                    card_status=card.status if card is not None else None,
                    evidence_exists=evidence is not None,
                    completed_actions=progress.completed_actions,
                    assignment_exists=assignment is not None,
                    future_week=onboarding_week.starts_on > reference_date,
                )
                required_actions_complete = bool(actions) and all(
                    not action.is_required or action.status is ActionStatus.COMPLETED
                    for action in actions
                )
                assignment_active = (
                    assignment is not None and assignment.status is AssignmentStatus.ACTIVE
                )

                return EmployeeDashboardResponse(
                    onboarding=EmployeeOnboardingResponse(
                        profile_id=profile.id,
                        overall_status=calculate_overall_status(
                            profile.start_date,
                            reference_date,
                        ),
                        week_number=onboarding_week.week_number,
                        stage=onboarding_week.stage,
                        week_status=week_status,
                        starts_on=onboarding_week.starts_on,
                        ends_on=onboarding_week.ends_on,
                    ),
                    core_value=CoreValueSummaryResponse(
                        id=core_value.id,
                        code=core_value.code,
                        name=core_value.name,
                        short_description=core_value.short_description,
                    ),
                    assignment=(
                        self._assignment_response(assignment)
                        if assignment is not None
                        else None
                    ),
                    actions=[self._action_detail_response(action) for action in actions],
                    progress=progress,
                    evidence=(
                        DashboardEvidenceSummaryResponse(
                            id=evidence.id,
                            submitted_at=self._response_datetime(evidence.submitted_at),
                        )
                        if evidence is not None
                        else None
                    ),
                    evidence_card=(
                        DashboardEvidenceCardSummaryResponse(id=card.id, status=card.status)
                        if card is not None
                        else None
                    ),
                    permissions=EmployeeDashboardPermissionsResponse(
                        can_update_actions=assignment_active and evidence is None,
                        can_submit_evidence=(
                            assignment_active
                            and evidence is None
                            and required_actions_complete
                        ),
                    ),
                )
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def update_action(
        self,
        *,
        employee_id: UUID,
        action_id: UUID,
        requested_status: ActionStatus,
        version: int,
    ) -> AssignedActionResponse:
        now = self._utc_now()
        try:
            async with transaction(self._session_factory) as session:
                row = (
                    await session.execute(
                        select(AssignedAction, WorkAssignment)
                        .join(
                            WorkAssignment,
                            WorkAssignment.id == AssignedAction.assignment_id,
                        )
                        .where(
                            AssignedAction.id == action_id,
                            WorkAssignment.employee_id == employee_id,
                        )
                        .with_for_update()
                    )
                ).one_or_none()
                if row is None:
                    self._raise_resource_not_found()
                action, assignment = row

                if action.status is requested_status:
                    return self._action_response(action)
                if assignment.status is not AssignmentStatus.ACTIVE:
                    raise ApiProblem(
                        status_code=409,
                        code="ASSIGNMENT_NOT_ACTIVE",
                        message="진행 중인 업무의 Action만 변경할 수 있습니다.",
                    )

                evidence_id = (
                    await session.execute(
                        select(EvidenceSubmission.id)
                        .where(EvidenceSubmission.assignment_id == assignment.id)
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if evidence_id is not None:
                    raise ApiProblem(
                        status_code=409,
                        code="ACTION_LOCKED_BY_EVIDENCE",
                        message="행동 근거를 제출한 뒤에는 Action을 변경할 수 없습니다.",
                    )
                if action.version != version:
                    raise ApiProblem(
                        status_code=409,
                        code="RESOURCE_VERSION_CONFLICT",
                        message="Action이 다른 요청에서 변경되었습니다. 새로고침해 주세요.",
                        details={"current_version": action.version},
                    )

                action.status = requested_status
                action.completed_at = (
                    now if requested_status is ActionStatus.COMPLETED else None
                )
                action.updated_at = now
                action.version += 1
                await session.flush()
                return self._action_response(action)
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def create_evidence(
        self,
        *,
        employee_id: UUID,
        payload: EvidenceCreateRequest,
    ) -> EvidenceResponse:
        self._validate_link_schemes(payload)
        submitted_at = self._utc_now()
        try:
            async with transaction(self._session_factory) as session:
                assignment = (
                    await session.execute(
                        select(WorkAssignment)
                        .where(
                            WorkAssignment.id == payload.assignment_id,
                            WorkAssignment.employee_id == employee_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if assignment is None:
                    self._raise_resource_not_found()
                if assignment.status is not AssignmentStatus.ACTIVE:
                    raise ApiProblem(
                        status_code=409,
                        code="ASSIGNMENT_NOT_ACTIVE",
                        message="진행 중인 업무에만 행동 근거를 제출할 수 있습니다.",
                    )

                existing_evidence = (
                    await session.execute(
                        select(EvidenceSubmission).where(
                            EvidenceSubmission.assignment_id == assignment.id
                        )
                    )
                ).scalar_one_or_none()
                if existing_evidence is not None:
                    raise ApiProblem(
                        status_code=409,
                        code="EVIDENCE_ALREADY_EXISTS",
                        message="이 업무에는 행동 근거가 이미 제출되었습니다.",
                        details={"evidence_id": str(existing_evidence.id)},
                    )

                actions = list(
                    (
                        await session.scalars(
                            select(AssignedAction)
                            .where(AssignedAction.assignment_id == assignment.id)
                            .order_by(AssignedAction.display_order)
                            .with_for_update()
                        )
                    ).all()
                )
                if any(
                    action.is_required and action.status is not ActionStatus.COMPLETED
                    for action in actions
                ):
                    raise ApiProblem(
                        status_code=409,
                        code="REQUIRED_ACTIONS_INCOMPLETE",
                        message="필수 Action을 모두 완료해 주세요.",
                    )

                actions_by_id = {action.id: action for action in actions}
                if any(action_id not in actions_by_id for action_id in payload.assigned_action_ids):
                    raise ApiProblem(
                        status_code=422,
                        code="ACTION_ASSIGNMENT_MISMATCH",
                        message="선택한 Action을 확인해 주세요.",
                    )
                if any(
                    actions_by_id[action_id].status is not ActionStatus.COMPLETED
                    for action_id in payload.assigned_action_ids
                ):
                    raise ApiProblem(
                        status_code=422,
                        code="ACTION_NOT_COMPLETED",
                        message="완료한 Action만 행동 근거로 선택할 수 있습니다.",
                    )

                evidence = EvidenceSubmission(
                    assignment_id=assignment.id,
                    employee_id=employee_id,
                    performed_action=payload.performed_action,
                    discovery=payload.discovery,
                    changed_judgment=payload.changed_judgment,
                    work_impact=payload.work_impact,
                    next_action=payload.next_action,
                    submitted_at=submitted_at,
                )
                session.add(evidence)
                await session.flush()

                session.add_all(
                    [
                        EvidenceSubmissionAction(
                            evidence_id=evidence.id,
                            assigned_action_id=action_id,
                        )
                        for action_id in payload.assigned_action_ids
                    ]
                )
                links = [
                    EvidenceLink(
                        evidence_id=evidence.id,
                        external_url=link.external_url,
                        title=link.title,
                        description=link.description,
                    )
                    for link in payload.links
                ]
                session.add_all(links)
                await session.flush()

                return EvidenceResponse(
                    id=evidence.id,
                    assignment_id=evidence.assignment_id,
                    assigned_action_ids=payload.assigned_action_ids,
                    performed_action=evidence.performed_action,
                    discovery=evidence.discovery,
                    changed_judgment=evidence.changed_judgment,
                    work_impact=evidence.work_impact,
                    next_action=evidence.next_action,
                    links=[self._link_response(link) for link in links],
                    submitted_at=self._response_datetime(evidence.submitted_at),
                )
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def get_evidence(
        self,
        *,
        employee_id: UUID,
        evidence_id: UUID,
    ) -> EvidenceResponse:
        try:
            async with self._session_factory() as session:
                evidence = (
                    await session.execute(
                        select(EvidenceSubmission).where(
                            EvidenceSubmission.id == evidence_id,
                            EvidenceSubmission.employee_id == employee_id,
                        )
                    )
                ).scalar_one_or_none()
                if evidence is None:
                    self._raise_resource_not_found()

                assigned_action_ids = list(
                    (
                        await session.scalars(
                            select(EvidenceSubmissionAction.assigned_action_id)
                            .join(
                                AssignedAction,
                                AssignedAction.id
                                == EvidenceSubmissionAction.assigned_action_id,
                            )
                            .where(EvidenceSubmissionAction.evidence_id == evidence.id)
                            .order_by(AssignedAction.display_order)
                        )
                    ).all()
                )
                links = list(
                    (
                        await session.scalars(
                            select(EvidenceLink)
                            .where(EvidenceLink.evidence_id == evidence.id)
                            .order_by(EvidenceLink.created_at, EvidenceLink.id)
                        )
                    ).all()
                )
                return EvidenceResponse(
                    id=evidence.id,
                    assignment_id=evidence.assignment_id,
                    assigned_action_ids=assigned_action_ids,
                    performed_action=evidence.performed_action,
                    discovery=evidence.discovery,
                    changed_judgment=evidence.changed_judgment,
                    work_impact=evidence.work_impact,
                    next_action=evidence.next_action,
                    links=[self._link_response(link) for link in links],
                    submitted_at=self._response_datetime(evidence.submitted_at),
                )
        except SQLAlchemyError:
            self._raise_database_unavailable()

    def _default_reference_date(self) -> date:
        if self._settings.app_env in {"demo", "test"}:
            return self._settings.demo_reference_date
        return datetime.now(ZoneInfo("Asia/Seoul")).date()

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("EmployeeService clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _response_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise RuntimeError("EmployeeService response datetime must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _validate_link_schemes(payload: EvidenceCreateRequest) -> None:
        for index, link in enumerate(payload.links):
            parsed = urlsplit(link.external_url)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
                raise ApiProblem(
                    status_code=422,
                    code="INVALID_LINK_SCHEME",
                    message="링크는 HTTP 또는 HTTPS 주소만 사용할 수 있습니다.",
                    field_errors=[
                        {
                            "field": f"links.{index}.external_url",
                            "reason": "HTTP 또는 HTTPS 주소를 입력해 주세요.",
                        }
                    ],
                )

    @staticmethod
    def _assignment_response(assignment: WorkAssignment) -> AssignmentSummaryResponse:
        return AssignmentSummaryResponse(
            id=assignment.id,
            title=assignment.title,
            description=assignment.description,
            work_type=assignment.work_type,
            start_date=assignment.start_date,
            due_date=assignment.due_date,
            status=assignment.status,
        )

    @staticmethod
    def _action_detail_response(action: AssignedAction) -> AssignedActionDetailResponse:
        return AssignedActionDetailResponse(
            id=action.id,
            text=action.action_text_snapshot,
            completion_criteria=action.completion_criteria_snapshot,
            recommended_evidence=[str(item) for item in action.recommended_evidence_snapshot],
            is_required=action.is_required,
            display_order=action.display_order,
            status=action.status,
            completed_at=EmployeeService._response_datetime(action.completed_at),
            version=action.version,
        )

    @staticmethod
    def _action_response(action: AssignedAction) -> AssignedActionResponse:
        return AssignedActionResponse(
            id=action.id,
            status=action.status,
            completed_at=EmployeeService._response_datetime(action.completed_at),
            version=action.version,
        )

    @staticmethod
    def _link_response(link: EvidenceLink) -> EvidenceLinkResponse:
        return EvidenceLinkResponse(
            id=link.id,
            external_url=link.external_url,
            title=link.title,
            description=link.description,
        )

    @staticmethod
    def _raise_resource_not_found() -> None:
        raise ApiProblem(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="리소스를 찾을 수 없습니다.",
        )

    @staticmethod
    def _raise_database_unavailable() -> None:
        raise ApiProblem(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="데이터베이스를 사용할 수 없습니다.",
        ) from None
