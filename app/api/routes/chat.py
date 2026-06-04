from __future__ import annotations

from fastapi import APIRouter, Depends
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


@router.post("", response_model=ChatResponse)
async def post_chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    session_id = request.session_id or generate_session_id()
    return chat_service.answer(request=request, session_id=session_id)


@router.post("/stream")
async def post_chat_stream(_: ChatRequest) -> None:
    raise AppError(
        error_code="not_implemented",
        message="流式问答接口尚未实现。",
        status_code=501,
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
