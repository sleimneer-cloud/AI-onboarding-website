from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    CsrfProtectedAuth,
    CurrentAuth,
    enforce_role,
)
from app.core.config import Settings, get_settings
from app.db.dependencies import SessionFactory
from app.models.enums import UserRole
from app.schemas.employee import (
    AssignedActionResponse,
    AssignedActionUpdateRequest,
    EmployeeDashboardResponse,
    EvidenceCreateRequest,
    EvidenceResponse,
)
from app.schemas.errors import ApiErrorResponse
from app.services.auth import AuthContext
from app.services.employee import EmployeeService

router = APIRouter(prefix="/api/v1", tags=["employee"])

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


def get_employee_service(
    session_factory: SessionFactory,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmployeeService:
    return EmployeeService(session_factory=session_factory, settings=settings)


EmployeeServiceDependency = Annotated[EmployeeService, Depends(get_employee_service)]


async def require_employee(context: CurrentAuth) -> AuthContext:
    enforce_role(context, frozenset({UserRole.EMPLOYEE}))
    return context


async def require_employee_csrf(context: CsrfProtectedAuth) -> AuthContext:
    enforce_role(context, frozenset({UserRole.EMPLOYEE}))
    return context


EmployeeAuth = Annotated[AuthContext, Depends(require_employee)]
EmployeeMutationAuth = Annotated[AuthContext, Depends(require_employee_csrf)]


@router.get(
    "/employee/dashboard",
    response_model=EmployeeDashboardResponse,
    responses=ERROR_RESPONSES,
)
async def employee_dashboard(
    context: EmployeeAuth,
    service: EmployeeServiceDependency,
) -> EmployeeDashboardResponse:
    return await service.get_dashboard(context.user.id)


@router.patch(
    "/assigned-actions/{action_id}",
    response_model=AssignedActionResponse,
    responses=ERROR_RESPONSES,
)
async def update_assigned_action(
    action_id: UUID,
    payload: AssignedActionUpdateRequest,
    context: EmployeeMutationAuth,
    service: EmployeeServiceDependency,
) -> AssignedActionResponse:
    return await service.update_action(
        employee_id=context.user.id,
        action_id=action_id,
        requested_status=payload.status,
        version=payload.version,
    )


@router.post(
    "/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_evidence(
    payload: EvidenceCreateRequest,
    context: EmployeeMutationAuth,
    service: EmployeeServiceDependency,
) -> EvidenceResponse:
    return await service.create_evidence(employee_id=context.user.id, payload=payload)


@router.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    responses=ERROR_RESPONSES,
)
async def get_evidence(
    evidence_id: UUID,
    context: EmployeeAuth,
    service: EmployeeServiceDependency,
) -> EvidenceResponse:
    return await service.get_evidence(
        employee_id=context.user.id,
        evidence_id=evidence_id,
    )
