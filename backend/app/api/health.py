from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.core.config import Settings, get_settings
from app.services.readiness import check_database_ready

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: Literal["ix-value-loop"]
    version: str


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Report process health without touching PostgreSQL or external providers."""

    return HealthResponse(status="ok", service="ix-value-loop", version=settings.app_version)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness(
    database_ready: Annotated[bool, Depends(check_database_ready)],
) -> ReadinessResponse | JSONResponse:
    """Report whether PostgreSQL can answer a bounded SELECT 1 probe."""

    if database_ready:
        return ReadinessResponse(status="ready", database="ok")

    payload = ReadinessResponse(status="not_ready", database="unavailable")
    return JSONResponse(status_code=503, content=payload.model_dump())
