from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from loguru import logger

from app.api.deps import (
    AppError,
    app_error_handler,
    request_validation_error_handler,
    unhandled_error_handler,
)
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        start_time = perf_counter()

        with logger.contextualize(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        ):
            logger.info("收到请求")
            response = await call_next(request)
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info("请求处理完成，status_code={} duration_ms={}", response.status_code, duration_ms)
            return response

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(ingest_router)

    @app.get("/", tags=["health"])
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "status": "ok"}

    return app


app = create_app()
