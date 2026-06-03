from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AppError
from app.core.config import get_settings
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatResumeRequest,
    ChatSessionResponse,
)
from app.schemas.common import UsageInfo
from app.services.context_budget_service import build_default_context_budget
from app.services.session_service import generate_session_id, validate_session_id

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def post_chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or generate_session_id()
    context_budget = build_default_context_budget(get_settings()) if request.debug_context else None

    return ChatResponse(
        session_id=session_id,
        answer="聊天主链路尚未实现，当前为骨架返回。",
        status="completed",
        sources=[],
        related_images=[],
        context_budget=context_budget,
        usage=UsageInfo(),
    )


@router.post("/stream")
async def post_chat_stream(_: ChatRequest) -> None:
    raise AppError(
        error_code="not_implemented",
        message="流式问答接口尚未实现。",
        status_code=501,
    )


@router.post("/resume", response_model=ChatResponse)
async def post_chat_resume(request: ChatResumeRequest) -> ChatResponse:
    return ChatResponse(
        session_id=request.session_id,
        answer="恢复会话主链路尚未实现，当前为骨架返回。",
        status="completed",
        sources=[],
        related_images=[],
        context_budget=None,
        usage=UsageInfo(),
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(session_id: str) -> ChatSessionResponse:
    try:
        validated_session_id = validate_session_id(session_id)
    except ValueError as exc:
        raise AppError(
            error_code="invalid_request",
            message=str(exc),
            status_code=400,
        ) from exc

    return ChatSessionResponse(
        session_id=validated_session_id,
        status="active",
    )
