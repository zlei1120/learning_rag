from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from uuid import uuid4

from sqlalchemy.orm import Session

from app.api.deps import AppError
from app.core.config import Settings, get_settings
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.memory_repository import MemoryRepository


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")


def generate_session_id() -> str:
    """生成前端可直接复用的会话标识。"""
    return f"sess_{uuid4().hex}"


def is_valid_session_id(session_id: str) -> bool:
    """判断会话标识是否符合公开接口约定。"""
    return bool(SESSION_ID_PATTERN.fullmatch(session_id))


def validate_session_id(session_id: str) -> str:
    """校验会话标识格式，不合法时抛出值错误供上层转换。"""
    if not is_valid_session_id(session_id):
        raise ValueError("session_id 格式非法，必须是 8 到 64 位字母、数字、下划线或中划线组合。")
    return session_id


def estimate_text_tokens(text: str) -> int:
    """用轻量启发式估算一段文本的大致 token 数。"""
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return 0
    return max(1, len(normalized) // 2)


@dataclass(slots=True)
class ConversationMessage:
    """进入多轮上下文窗口的消息结构。"""

    message_id: str
    role: str
    content: str
    message_index: int
    token_estimate: int | None = None


@dataclass(slots=True)
class SessionContext:
    """问答链路使用的会话上下文快照。"""

    session_row_id: str
    session_id: str
    user_key: str | None
    status: str
    summary_text: str | None
    recent_messages: list[ConversationMessage]
    created_at: datetime | None
    updated_at: datetime | None
    last_message_at: datetime | None
    last_checkpoint_ref: str | None


class SessionService:
    """管理会话线程、最近消息和会话查询。"""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        chat_session_repository: ChatSessionRepository | None = None,
        chat_message_repository: ChatMessageRepository | None = None,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.chat_session_repository = chat_session_repository or ChatSessionRepository(session)
        self.chat_message_repository = chat_message_repository or ChatMessageRepository(session)
        self.memory_repository = memory_repository or MemoryRepository(session)

    def get_or_create_context(self, *, session_id: str, user_key: str | None = None) -> SessionContext:
        """读取或创建会话，并返回当前轮可用的上下文快照。"""
        chat_session = self.chat_session_repository.get_or_create(session_id=session_id, user_key=user_key)
        summary_record = self.memory_repository.get_latest_session_summary(chat_session.id)
        summary_text = summary_record.content if summary_record else chat_session.summary_text

        recent_messages = self.chat_message_repository.list_recent(
            chat_session.id,
            limit=self.settings.chat_history_message_limit,
        )
        trimmed_messages = self._trim_messages_to_budget(recent_messages)
        self.chat_message_repository.mark_context_window(
            chat_session_id=chat_session.id,
            included_message_ids=[message.id for message in trimmed_messages],
        )
        return self._build_context(chat_session, trimmed_messages, summary_text)

    def record_exchange(
        self,
        *,
        session_id: str,
        user_key: str | None,
        user_message: str,
        assistant_message: str,
        source_payload: dict[str, object] | None = None,
        checkpoint_ref: str | None = None,
    ) -> SessionContext:
        """持久化当前轮的用户消息和助手回答。"""
        chat_session = self.chat_session_repository.get_or_create(session_id=session_id, user_key=user_key)
        next_index = self.chat_message_repository.get_next_message_index(chat_session.id)
        self.chat_message_repository.create_message(
            chat_session_id=chat_session.id,
            message_index=next_index,
            role="user",
            content=user_message,
            token_estimate=estimate_text_tokens(user_message),
        )
        assistant_index = next_index + 1
        self.chat_message_repository.create_message(
            chat_session_id=chat_session.id,
            message_index=assistant_index,
            role="assistant",
            content=assistant_message,
            source_payload_json=source_payload,
            token_estimate=estimate_text_tokens(assistant_message),
        )
        resolved_checkpoint_ref = checkpoint_ref or f"{session_id}:{assistant_index}"
        self.chat_session_repository.touch(chat_session, checkpoint_ref=resolved_checkpoint_ref)
        return self.get_or_create_context(session_id=session_id, user_key=user_key)

    def build_retrieval_query(self, *, question: str, session_context: SessionContext) -> str:
        """根据会话摘要和最近消息构造更稳的检索查询。"""
        parts: list[str] = []

        if session_context.summary_text:
            parts.append(f"会话摘要：{self._truncate_text(session_context.summary_text, self.settings.chat_summary_max_chars)}")

        recent_user_messages = [
            message.content
            for message in session_context.recent_messages
            if message.role == "user"
        ]
        if recent_user_messages:
            joined_messages = "；".join(
                self._truncate_text(content, 120)
                for content in recent_user_messages[-2:]
            )
            parts.append(f"最近问题：{joined_messages}")

        parts.append(f"当前问题：{question}")
        return "\n".join(parts)

    def get_session_response(self, *, session_id: str):
        """返回会话查询接口需要的元数据。"""
        from app.schemas.chat import ChatSessionResponse

        chat_session = self.chat_session_repository.get_by_public_session_id(session_id)
        if chat_session is None:
            raise AppError(
                error_code="not_found",
                message="找不到对应的会话。",
                status_code=404,
            )

        summary_record = self.memory_repository.get_latest_session_summary(chat_session.id)
        summary_text = summary_record.content if summary_record else chat_session.summary_text
        return ChatSessionResponse(
            session_id=chat_session.session_id,
            status=chat_session.status,
            summary=summary_text,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
            last_message_at=chat_session.last_message_at,
        )

    def _build_context(
        self,
        chat_session: ChatSession,
        recent_messages: list[ChatMessage],
        summary_text: str | None,
    ) -> SessionContext:
        """把 ORM 会话对象转换为问答链路快照。"""
        return SessionContext(
            session_row_id=chat_session.id,
            session_id=chat_session.session_id,
            user_key=chat_session.user_key,
            status=chat_session.status,
            summary_text=summary_text,
            recent_messages=[
                ConversationMessage(
                    message_id=message.id,
                    role=message.role,
                    content=message.content,
                    message_index=message.message_index,
                    token_estimate=message.token_estimate,
                )
                for message in recent_messages
            ],
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
            last_message_at=chat_session.last_message_at,
            last_checkpoint_ref=chat_session.last_checkpoint_ref,
        )

    def _trim_messages_to_budget(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """按最近消息预算保留真正进入当前轮上下文的消息。"""
        if not messages:
            return []

        selected_messages: list[ChatMessage] = []
        used_tokens = 0
        budget_tokens = self.settings.chat_context_recent_messages_tokens

        for message in reversed(messages):
            token_cost = message.token_estimate or estimate_text_tokens(message.content)
            if selected_messages and used_tokens + token_cost > budget_tokens:
                continue
            if not selected_messages and token_cost > budget_tokens:
                selected_messages.append(message)
                break

            selected_messages.append(message)
            used_tokens += token_cost

        selected_messages.reverse()
        return selected_messages

    @staticmethod
    def _truncate_text(text: str, max_length: int) -> str:
        """裁剪说明文字，避免检索查询被会话历史淹没。"""
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[:max_length].rstrip()}..."
