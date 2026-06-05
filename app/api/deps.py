from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

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


def _get_request_id(request: Request) -> str | None:
    """优先读取当前请求链路标识。"""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    if request_id is None:
        return None
    return str(request_id)


def _merge_error_details(request: Request, details: dict[str, object] | None) -> dict[str, object] | None:
    """为错误响应补充统一链路字段。"""
    merged_details = dict(details or {})
    request_id = _get_request_id(request)
    if request_id:
        merged_details.setdefault("request_id", request_id)
    return merged_details or None


def _build_error_response(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    """构造统一错误结构。"""
    payload = ErrorResponse(
        error_code=error_code,
        message=message,
        details=_merge_error_details(request, details),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "业务异常，status_code={} error_code={} message={}",
        exc.status_code,
        exc.error_code,
        exc.message,
    )
    return _build_error_response(
        request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details or None,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常，exception_type={}", exc.__class__.__name__)
    return _build_error_response(
        request,
        status_code=500,
        error_code="internal_error",
        message="服务内部发生未处理异常。",
        details={"exception_type": exc.__class__.__name__},
    )


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("数据库异常，exception_type={}", exc.__class__.__name__)
    return _build_error_response(
        request,
        status_code=503,
        error_code="database_unavailable",
        message="数据库暂时不可用，请确认 PostgreSQL 已启动且 DATABASE_URL 配置正确。",
        details={"exception_type": exc.__class__.__name__},
    )


async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("请求参数校验失败，error_count={}", len(exc.errors()))
    return _build_error_response(
        request,
        status_code=400,
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


async def lifespan_dependency() -> AsyncIterator[None]:
    """为后续共享资源预留的生命周期依赖。"""
    yield
