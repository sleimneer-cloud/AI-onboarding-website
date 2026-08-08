from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ApiProblem
from app.schemas.errors import ApiErrorDetail, ApiErrorResponse, FieldError

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = str(uuid4())
        request.state.request_id = request_id
    return request_id


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: list[FieldError] | None = None,
    details: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    payload = ApiErrorResponse(
        error=ApiErrorDetail(
            code=code,
            message=message,
            field_errors=field_errors or [],
            details=details or {},
            request_id=request_id,
        )
    )
    response_headers = {"X-Request-ID": request_id}
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=response_headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def api_problem_handler(request: Request, exc: ApiProblem) -> JSONResponse:
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            field_errors=[FieldError.model_validate(item) for item in exc.field_errors],
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = exc.errors()
        card_content_error = request.method == "PATCH" and request.url.path.startswith(
            "/api/v1/evidence-cards/"
        ) and any(
            error.get("type") == "card_schema_invalid"
            or tuple(error.get("loc", ()))[:2] == ("body", "content")
            for error in errors
        )
        if card_content_error:
            return _error_response(
                request,
                status_code=422,
                code="CARD_SCHEMA_INVALID",
                message="Evidence Card 형식을 확인해 주세요.",
            )
        invalid_json = any(error.get("type") == "json_invalid" for error in errors)
        if invalid_json:
            return _error_response(
                request,
                status_code=400,
                code="INVALID_JSON",
                message="요청 JSON 형식을 확인해 주세요.",
            )

        field_errors = []
        for error in errors:
            location = [str(part) for part in error.get("loc", ()) if part != "body"]
            field_errors.append(
                FieldError(
                    field=".".join(location) or "body",
                    reason=str(error.get("msg", "입력값을 확인해 주세요.")),
                )
            )
        return _error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="입력값을 확인해 주세요.",
            field_errors=field_errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/"):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "INTERNAL_ERROR"
        message = (
            "리소스를 찾을 수 없습니다."
            if exc.status_code == 404
            else "요청을 처리할 수 없습니다."
        )
        return _error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=message,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_api_error request_id=%s exception_type=%s",
            _request_id(request),
            type(exc).__name__,
        )
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="요청을 처리하는 중 오류가 발생했습니다.",
        )
