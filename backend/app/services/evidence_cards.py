from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ApiProblem
from app.db.session import transaction
from app.models.actions import AssignedAction, WorkAssignment
from app.models.enums import EvidenceCardStatus
from app.models.evidence import (
    EvidenceCard,
    EvidenceLink,
    EvidenceSubmission,
    EvidenceSubmissionAction,
)
from app.models.onboarding import CoreValue, OnboardingWeek
from app.schemas.cards import (
    EvidenceCardGenerationResponse,
    EvidenceCardPermissionsResponse,
    EvidenceCardResponse,
)
from app.schemas.llm import (
    CardContentV1,
    CardSourceReferenceError,
    EvidenceCardGenerationInputV1,
    GenerationActionV1,
    GenerationAssignmentV1,
    GenerationCoreValueV1,
    GenerationEvidenceFieldV1,
    GenerationEvidenceV1,
    GenerationLinkV1,
    GenerationNextActionFieldV1,
    GenerationOnboardingV1,
    validate_card_source_refs,
)
from app.services.evidence_generation import (
    EvidenceGenerationOrchestrator,
    GenerationOutcome,
)


@dataclass(frozen=True)
class CardGenerationResult:
    card: EvidenceCardResponse
    status_code: int
    retry_after_seconds: int | None = None


class EvidenceCardService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        generator: EvidenceGenerationOrchestrator,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._generator = generator

    async def create_or_retry_card(
        self,
        *,
        employee_id: UUID,
        evidence_id: UUID,
        request_id: UUID,
    ) -> CardGenerationResult:
        created = False
        generation_input: EvidenceCardGenerationInputV1 | None = None
        card_id: UUID | None = None
        try:
            async with transaction(self._session_factory) as session:
                bundle = await self._load_generation_bundle(
                    session,
                    employee_id=employee_id,
                    evidence_id=evidence_id,
                    lock=True,
                )
                if bundle is None:
                    self._raise_resource_not_found()
                evidence, assignment, onboarding_week, core_value = bundle

                card = (
                    await session.execute(
                        select(EvidenceCard)
                        .where(EvidenceCard.evidence_id == evidence.id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if card is not None:
                    if card.status is EvidenceCardStatus.AI_PROCESSING:
                        return CardGenerationResult(
                            card=self._card_response(card),
                            status_code=202,
                            retry_after_seconds=1,
                        )
                    if card.status is not EvidenceCardStatus.GENERATION_FAILED:
                        return CardGenerationResult(
                            card=self._card_response(card),
                            status_code=200,
                        )
                    card.status = EvidenceCardStatus.AI_PROCESSING
                    card.generated_content_json = None
                    card.final_content_json = None
                    card.generated_by = None
                    card.model_name = None
                    card.prompt_version = self._settings.ai_prompt_version
                    card.schema_version = self._settings.ai_schema_version
                    card.generation_latency_ms = None
                    card.last_error_code = None
                else:
                    created = True
                    card = EvidenceCard(
                        evidence_id=evidence.id,
                        status=EvidenceCardStatus.AI_PROCESSING,
                        prompt_version=self._settings.ai_prompt_version,
                        schema_version=self._settings.ai_schema_version,
                        generation_attempts=0,
                        version=1,
                    )
                    session.add(card)

                generation_input = await self._build_generation_input(
                    session,
                    request_id=request_id,
                    evidence=evidence,
                    assignment=assignment,
                    onboarding_week=onboarding_week,
                    core_value=core_value,
                )
                await session.flush()
                card_id = card.id
        except SQLAlchemyError:
            self._raise_database_unavailable()

        if generation_input is None or card_id is None:
            raise RuntimeError("Card generation preparation did not produce an input")

        outcome = await self._generator.generate(generation_input)
        try:
            async with transaction(self._session_factory) as session:
                card = (
                    await session.execute(
                        select(EvidenceCard)
                        .where(EvidenceCard.id == card_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if card is None:
                    self._raise_resource_not_found()
                self._apply_generation_outcome(card, outcome)
                await session.flush()
                response = self._card_response(card)
        except SQLAlchemyError:
            self._raise_database_unavailable()

        return CardGenerationResult(
            card=response,
            status_code=201 if created else 200,
        )

    async def get_card(self, *, employee_id: UUID, card_id: UUID) -> EvidenceCardResponse:
        try:
            async with self._session_factory() as session:
                card = await self._load_owned_card(
                    session,
                    employee_id=employee_id,
                    card_id=card_id,
                )
                if card is None:
                    self._raise_resource_not_found()
                return self._card_response(card)
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def update_card(
        self,
        *,
        employee_id: UUID,
        card_id: UUID,
        version: int,
        content: CardContentV1,
    ) -> EvidenceCardResponse:
        try:
            async with transaction(self._session_factory) as session:
                card = await self._load_owned_card(
                    session,
                    employee_id=employee_id,
                    card_id=card_id,
                    lock=True,
                )
                if card is None:
                    self._raise_resource_not_found()
                if card.status is not EvidenceCardStatus.USER_REVIEW:
                    raise ApiProblem(
                        status_code=409,
                        code="CARD_NOT_EDITABLE",
                        message="확인 중인 Evidence Card만 수정할 수 있습니다.",
                    )
                if card.version != version:
                    self._raise_version_conflict(card.version)
                self._validate_user_content(
                    content,
                    await self._allowed_source_refs(session, card.evidence_id),
                )
                card.final_content_json = content.model_dump(mode="json")
                card.version += 1
                await session.flush()
                return self._card_response(card)
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def confirm_card(
        self,
        *,
        employee_id: UUID,
        card_id: UUID,
        version: int,
    ) -> EvidenceCardResponse:
        try:
            async with transaction(self._session_factory) as session:
                card = await self._load_owned_card(
                    session,
                    employee_id=employee_id,
                    card_id=card_id,
                    lock=True,
                )
                if card is None:
                    self._raise_resource_not_found()
                if card.status is EvidenceCardStatus.USER_CONFIRMED:
                    return self._card_response(card)
                if card.status is not EvidenceCardStatus.USER_REVIEW:
                    raise ApiProblem(
                        status_code=409,
                        code="INVALID_CARD_TRANSITION",
                        message="현재 상태에서는 Evidence Card를 확정할 수 없습니다.",
                    )
                if card.version != version:
                    self._raise_version_conflict(card.version)
                try:
                    content = CardContentV1.model_validate(card.final_content_json)
                except ValidationError as exc:
                    raise ApiProblem(
                        status_code=422,
                        code="CARD_SCHEMA_INVALID",
                        message="Evidence Card 형식을 확인해 주세요.",
                    ) from exc
                self._validate_user_content(
                    content,
                    await self._allowed_source_refs(session, card.evidence_id),
                )
                card.status = EvidenceCardStatus.USER_CONFIRMED
                card.confirmed_at = datetime.now(UTC)
                card.version += 1
                await session.flush()
                return self._card_response(card)
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def _load_generation_bundle(
        self,
        session: AsyncSession,
        *,
        employee_id: UUID,
        evidence_id: UUID,
        lock: bool,
    ) -> tuple[EvidenceSubmission, WorkAssignment, OnboardingWeek, CoreValue] | None:
        query = (
            select(EvidenceSubmission, WorkAssignment, OnboardingWeek, CoreValue)
            .join(WorkAssignment, WorkAssignment.id == EvidenceSubmission.assignment_id)
            .join(OnboardingWeek, OnboardingWeek.id == WorkAssignment.onboarding_week_id)
            .join(CoreValue, CoreValue.id == OnboardingWeek.core_value_id)
            .where(
                EvidenceSubmission.id == evidence_id,
                EvidenceSubmission.employee_id == employee_id,
            )
        )
        if lock:
            query = query.with_for_update(of=EvidenceSubmission)
        return (await session.execute(query)).one_or_none()

    async def _build_generation_input(
        self,
        session: AsyncSession,
        *,
        request_id: UUID,
        evidence: EvidenceSubmission,
        assignment: WorkAssignment,
        onboarding_week: OnboardingWeek,
        core_value: CoreValue,
    ) -> EvidenceCardGenerationInputV1:
        actions = list(
            (
                await session.scalars(
                    select(AssignedAction)
                    .join(
                        EvidenceSubmissionAction,
                        EvidenceSubmissionAction.assigned_action_id == AssignedAction.id,
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
        return EvidenceCardGenerationInputV1(
            schema_version="1.0",
            request_id=request_id,
            language="ko-KR",
            core_value=GenerationCoreValueV1(
                code=core_value.code,
                name=core_value.name,
                definition=core_value.full_description,
            ),
            onboarding=GenerationOnboardingV1(
                week_number=onboarding_week.week_number,
                stage=onboarding_week.stage,
            ),
            assignment=GenerationAssignmentV1(
                id=assignment.id,
                title=assignment.title,
                description=assignment.description,
                work_type=assignment.work_type,
                description_source_ref="assignment.description",
            ),
            actions=[
                GenerationActionV1(
                    id=action.id,
                    text=action.action_text_snapshot,
                    completion_criteria=action.completion_criteria_snapshot,
                    source_ref=f"action:{action.id}",
                )
                for action in actions
            ],
            evidence=GenerationEvidenceV1(
                id=evidence.id,
                performed_action=GenerationEvidenceFieldV1(
                    text=evidence.performed_action,
                    source_ref="evidence.performed_action",
                ),
                discovery=GenerationEvidenceFieldV1(
                    text=evidence.discovery,
                    source_ref="evidence.discovery",
                ),
                changed_judgment=GenerationEvidenceFieldV1(
                    text=evidence.changed_judgment,
                    source_ref="evidence.changed_judgment",
                ),
                work_impact=GenerationEvidenceFieldV1(
                    text=evidence.work_impact,
                    source_ref="evidence.work_impact",
                ),
                next_action=GenerationNextActionFieldV1(
                    text=evidence.next_action,
                    source_ref="evidence.next_action",
                ),
                links=[
                    GenerationLinkV1(
                        id=link.id,
                        title=link.title,
                        description=link.description,
                        source_ref=f"link:{link.id}",
                    )
                    for link in links
                ],
            ),
        )

    async def _load_owned_card(
        self,
        session: AsyncSession,
        *,
        employee_id: UUID,
        card_id: UUID,
        lock: bool = False,
    ) -> EvidenceCard | None:
        query = (
            select(EvidenceCard)
            .join(
                EvidenceSubmission,
                EvidenceSubmission.id == EvidenceCard.evidence_id,
            )
            .where(
                EvidenceCard.id == card_id,
                EvidenceSubmission.employee_id == employee_id,
            )
        )
        if lock:
            query = query.with_for_update(of=EvidenceCard)
        return (await session.execute(query)).scalar_one_or_none()

    async def _allowed_source_refs(
        self,
        session: AsyncSession,
        evidence_id: UUID,
    ) -> frozenset[str]:
        action_ids = list(
            (
                await session.scalars(
                    select(EvidenceSubmissionAction.assigned_action_id).where(
                        EvidenceSubmissionAction.evidence_id == evidence_id
                    )
                )
            ).all()
        )
        link_ids = list(
            (
                await session.scalars(
                    select(EvidenceLink.id).where(EvidenceLink.evidence_id == evidence_id)
                )
            ).all()
        )
        return frozenset(
            {
                "core_value.definition",
                "assignment.description",
                "evidence.performed_action",
                "evidence.discovery",
                "evidence.changed_judgment",
                "evidence.work_impact",
                "evidence.next_action",
                *(f"action:{action_id}" for action_id in action_ids),
                *(f"link:{link_id}" for link_id in link_ids),
            }
        )

    def _apply_generation_outcome(
        self,
        card: EvidenceCard,
        outcome: GenerationOutcome,
    ) -> None:
        card.generation_attempts = outcome.attempts
        card.generation_latency_ms = outcome.latency_ms
        card.last_error_code = outcome.last_error_code
        if outcome.content is None:
            card.status = EvidenceCardStatus.GENERATION_FAILED
            card.generated_content_json = None
            card.final_content_json = None
            card.generated_by = None
            card.model_name = None
            return

        payload = outcome.content.model_dump(mode="json")
        card.generated_content_json = copy.deepcopy(payload)
        card.final_content_json = copy.deepcopy(payload)
        card.generated_by = outcome.provider
        card.model_name = outcome.model_name
        card.status = EvidenceCardStatus.USER_REVIEW

    @staticmethod
    def _validate_user_content(
        content: CardContentV1,
        allowed_source_refs: frozenset[str],
    ) -> None:
        try:
            validate_card_source_refs(content, allowed_source_refs)
        except CardSourceReferenceError as exc:
            raise ApiProblem(
                status_code=422,
                code="CARD_SOURCE_REF_INVALID",
                message="Evidence Card의 근거 연결을 확인해 주세요.",
            ) from exc

    @staticmethod
    def _card_response(card: EvidenceCard) -> EvidenceCardResponse:
        content = (
            CardContentV1.model_validate(card.final_content_json)
            if card.final_content_json is not None
            else None
        )
        return EvidenceCardResponse(
            id=card.id,
            evidence_id=card.evidence_id,
            status=card.status,
            content=content,
            generation=EvidenceCardGenerationResponse(
                provider=card.generated_by,
                model_name=card.model_name,
                prompt_version=card.prompt_version,
                schema_version=card.schema_version,
                latency_ms=card.generation_latency_ms,
            ),
            version=card.version,
            confirmed_at=card.confirmed_at,
            manager_reviewed_at=card.manager_reviewed_at,
            permissions=EvidenceCardPermissionsResponse(
                can_edit=card.status is EvidenceCardStatus.USER_REVIEW,
                can_confirm=card.status is EvidenceCardStatus.USER_REVIEW,
                can_retry=card.status is EvidenceCardStatus.GENERATION_FAILED,
            ),
        )

    @staticmethod
    def _raise_resource_not_found() -> None:
        raise ApiProblem(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="리소스를 찾을 수 없습니다.",
        )

    @staticmethod
    def _raise_version_conflict(current_version: int) -> None:
        raise ApiProblem(
            status_code=409,
            code="RESOURCE_VERSION_CONFLICT",
            message="Evidence Card가 다른 요청에서 변경되었습니다. 새로고침해 주세요.",
            details={"current_version": current_version},
        )

    @staticmethod
    def _raise_database_unavailable() -> None:
        raise ApiProblem(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="데이터베이스를 사용할 수 없습니다.",
        )
