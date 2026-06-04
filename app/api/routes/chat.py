from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import AppError
from app.core.database import get_db_session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatResumeRequest,
    ChatSessionResponse,
)
from app.services.chat_service import ChatService
from app.services.session_service import SessionService, generate_session_id, validate_session_id

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def get_chat_service(session: Session = Depends(get_db_session)) -> ChatService:
    """为问答接口提供服务实例。"""
    return ChatService(session)


def get_session_service(session: Session = Depends(get_db_session)) -> SessionService:
    """为会话接口提供服务实例。"""
    return SessionService(session)


def _format_sse_event(*, event: str, payload: dict[str, object]) -> str:
    """把结构化事件编码成 SSE 文本。"""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_chat_response(response: ChatResponse) -> AsyncIterator[str]:
    """把完整问答结果拆成前端可消费的 SSE 事件流。"""
    answer = response.answer or ""
    collected_answer = ""
    chunk_size = 18

    for index in range(0, len(answer), chunk_size):
        delta = answer[index : index + chunk_size]
        collected_answer += delta
        yield _format_sse_event(
            event="message.delta",
            payload={
                "session_id": response.session_id,
                "delta": delta,
                "accumulated": collected_answer,
            },
        )
        await asyncio.sleep(0)

    for source in response.sources:
        yield _format_sse_event(
            event="source",
            payload=source.model_dump(exclude_none=True),
        )
        await asyncio.sleep(0)

    for image in response.related_images:
        yield _format_sse_event(
            event="related_image",
            payload=image.model_dump(exclude_none=True),
        )
        await asyncio.sleep(0)

    if response.context_budget is not None:
        yield _format_sse_event(
            event="context_budget",
            payload=response.context_budget.model_dump(exclude_none=True),
        )
        await asyncio.sleep(0)

    if response.usage is not None:
        yield _format_sse_event(
            event="usage",
            payload=response.usage.model_dump(exclude_none=True),
        )
        await asyncio.sleep(0)

    yield _format_sse_event(
        event="message.completed",
        payload=response.model_dump(mode="json", exclude_none=True),
    )


@router.post("", response_model=ChatResponse)
async def post_chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    session_id = request.session_id or generate_session_id()
    return chat_service.answer(request=request, session_id=session_id)


@router.post("/stream")
async def post_chat_stream(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    session_id = request.session_id or generate_session_id()
    response = chat_service.answer(request=request, session_id=session_id)
    return StreamingResponse(
        _stream_chat_response(response),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/resume", response_model=ChatResponse)
async def post_chat_resume(
    request: ChatResumeRequest,
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
) -> ChatResponse:
    session_service.get_session_response(session_id=request.session_id)
    return chat_service.answer(
        request=ChatRequest(session_id=request.session_id, message=request.message),
        session_id=request.session_id,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> ChatSessionResponse:
    try:
        validated_session_id = validate_session_id(session_id)
    except ValueError as exc:
        raise AppError(
            error_code="invalid_request",
            message=str(exc),
            status_code=400,
        ) from exc

    return session_service.get_session_response(session_id=validated_session_id)
