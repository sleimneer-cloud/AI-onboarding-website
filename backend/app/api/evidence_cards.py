from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.employee import EmployeeAuth, EmployeeMutationAuth
from app.core.config import Settings, get_settings
from app.db.dependencies import SessionFactory
from app.schemas.cards import (
    EvidenceCardConfirmRequest,
    EvidenceCardResponse,
    EvidenceCardUpdateRequest,
)
from app.schemas.errors import ApiErrorResponse
from app.services.evidence_cards import EvidenceCardService
from app.services.evidence_generation import build_generation_orchestrator

router = APIRouter(prefix="/api/v1", tags=["evidence-cards"])

ERROR_RESPONSES = {
    400: {"model": ApiErrorResponse},
    401: {"model": ApiErrorResponse},
    403: {"model": ApiErrorResponse},
    404: {"model": ApiErrorResponse},
    409: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
    500: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}


def get_evidence_card_service(
    session_factory: SessionFactory,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EvidenceCardService:
    return EvidenceCardService(
        session_factory=session_factory,
        settings=settings,
        generator=build_generation_orchestrator(settings),
    )


EvidenceCardServiceDependency = Annotated[
    EvidenceCardService,
    Depends(get_evidence_card_service),
]


@router.post(
    "/evidence/{evidence_id}/card",
    response_model=EvidenceCardResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **ERROR_RESPONSES,
        200: {"model": EvidenceCardResponse},
        202: {"model": EvidenceCardResponse},
    },
)
async def create_evidence_card(
    evidence_id: UUID,
    request: Request,
    response: Response,
    context: EmployeeMutationAuth,
    service: EvidenceCardServiceDependency,
) -> EvidenceCardResponse:
    result = await service.create_or_retry_card(
        employee_id=context.user.id,
        evidence_id=evidence_id,
        request_id=UUID(request.state.request_id),
    )
    response.status_code = result.status_code
    if result.retry_after_seconds is not None:
        response.headers["Retry-After"] = str(result.retry_after_seconds)
    return result.card


@router.get(
    "/evidence-cards/{card_id}",
    response_model=EvidenceCardResponse,
    responses=ERROR_RESPONSES,
)
async def get_evidence_card(
    card_id: UUID,
    context: EmployeeAuth,
    service: EvidenceCardServiceDependency,
) -> EvidenceCardResponse:
    return await service.get_card(employee_id=context.user.id, card_id=card_id)


@router.patch(
    "/evidence-cards/{card_id}",
    response_model=EvidenceCardResponse,
    responses=ERROR_RESPONSES,
)
async def update_evidence_card(
    card_id: UUID,
    payload: EvidenceCardUpdateRequest,
    context: EmployeeMutationAuth,
    service: EvidenceCardServiceDependency,
) -> EvidenceCardResponse:
    return await service.update_card(
        employee_id=context.user.id,
        card_id=card_id,
        version=payload.version,
        content=payload.content,
    )


@router.post(
    "/evidence-cards/{card_id}/confirm",
    response_model=EvidenceCardResponse,
    responses=ERROR_RESPONSES,
)
async def confirm_evidence_card(
    card_id: UUID,
    payload: EvidenceCardConfirmRequest,
    context: EmployeeMutationAuth,
    service: EvidenceCardServiceDependency,
) -> EvidenceCardResponse:
    return await service.confirm_card(
        employee_id=context.user.id,
        card_id=card_id,
        version=payload.version,
    )
