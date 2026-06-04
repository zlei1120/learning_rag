from __future__ import annotations

from hashlib import sha256

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.session_service import SessionContext


class MemoryService:
    """维护会话摘要记忆，并为后续长期记忆预留边界。"""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        chat_message_repository: ChatMessageRepository | None = None,
        chat_session_repository: ChatSessionRepository | None = None,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.chat_message_repository = chat_message_repository or ChatMessageRepository(session)
        self.chat_session_repository = chat_session_repository or ChatSessionRepository(session)
        self.memory_repository = memory_repository or MemoryRepository(session)

    def refresh_session_summary(self, session_context: SessionContext) -> str | None:
        """根据较早的对话历史更新当前会话摘要。"""
        messages = self.chat_message_repository.list_all(session_context.session_row_id)
        if len(messages) <= self.settings.chat_history_message_limit:
            self.memory_repository.delete_session_summary(session_context.session_row_id)
            chat_session = self.chat_session_repository.get_by_id(session_context.session_row_id)
            if chat_session is not None:
                self.chat_session_repository.update_summary(chat_session, None)
            return None

        summary_messages = messages[:-self.settings.chat_history_message_limit]
        summary_text = self._build_summary_text(summary_messages, max_length=self.settings.chat_summary_max_chars)
        chat_session = self.chat_session_repository.get_by_id(session_context.session_row_id)
        if chat_session is None:
            return summary_text

        self.memory_repository.upsert_session_summary(
            chat_session_id=session_context.session_row_id,
            user_key=chat_session.user_key,
            content=summary_text,
            content_hash=sha256(summary_text.encode("utf-8")).hexdigest(),
        )
        self.chat_session_repository.update_summary(chat_session, summary_text)
        return summary_text

    @staticmethod
    def _build_summary_text(messages: list[object], *, max_length: int) -> str:
        """把较早消息压缩成一段可控长度的会话摘要。"""
        lines: list[str] = []
        for message in messages[-8:]:
            role = getattr(message, "role", "unknown")
            label = "用户" if role == "user" else "助手"
            content = " ".join(str(getattr(message, "content", "")).split()).strip()
            if not content:
                continue
            if len(content) > 90:
                content = f"{content[:90].rstrip()}..."
            lines.append(f"{label}：{content}")

        summary = "；".join(lines).strip()
        if len(summary) <= max_length:
            return summary
        return f"{summary[:max_length].rstrip()}..."
