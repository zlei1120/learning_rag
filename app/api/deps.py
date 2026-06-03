from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorResponse


class AppError(Exception):
    """带有 HTTP 语义的基础业务异常。"""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    payload = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details or None,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(exclude_none=True))


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    payload = ErrorResponse(
        error_code="internal_error",
        message="服务内部发生未处理异常。",
        details={"exception_type": exc.__class__.__name__},
    )
    return JSONResponse(status_code=500, content=payload.model_dump(exclude_none=True))


async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    payload = ErrorResponse(
        error_code="invalid_request",
        message="请求参数校验失败。",
        details={
            "errors": [
                {
                    "field": ".".join(str(item) for item in error["loc"] if item != "body"),
                    "message": error["msg"],
                    "error_type": error["type"],
                }
                for error in exc.errors()
            ]
        },
    )
    return JSONResponse(status_code=400, content=payload.model_dump(exclude_none=True))


async def lifespan_dependency() -> AsyncIterator[None]:
    """为后续共享资源预留的生命周期依赖。"""
    yield
