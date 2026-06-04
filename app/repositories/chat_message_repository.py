from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage


class ChatMessageRepository:
    """管理会话消息读写。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, chat_session_id: str) -> list[ChatMessage]:
        """按时间顺序读取整个会话的全部消息。"""
        statement = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.message_index.asc(), ChatMessage.created_at.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_recent(self, chat_session_id: str, *, limit: int) -> list[ChatMessage]:
        """读取最近若干条消息，并保持时间正序。"""
        statement = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.message_index.desc(), ChatMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(self.session.execute(statement).scalars().all())
        messages.reverse()
        return messages

    def get_next_message_index(self, chat_session_id: str) -> int:
        """返回当前会话下一条消息应使用的顺序号。"""
        statement = select(func.max(ChatMessage.message_index)).where(ChatMessage.chat_session_id == chat_session_id)
        current_max = self.session.execute(statement).scalar_one()
        return int(current_max or 0) + 1

    def create_message(
        self,
        *,
        chat_session_id: str,
        message_index: int,
        role: str,
        content: str,
        content_summary: str | None = None,
        source_payload_json: dict[str, object] | None = None,
        budget_included: bool = False,
        trimmed: bool = False,
        token_estimate: int | None = None,
    ) -> ChatMessage:
        """写入一条会话消息。"""
        message = ChatMessage(
            chat_session_id=chat_session_id,
            message_index=message_index,
            role=role,
            content=content,
            content_summary=content_summary,
            source_payload_json=source_payload_json,
            budget_included=budget_included,
            trimmed=trimmed,
            token_estimate=token_estimate,
        )
        self.session.add(message)
        self.session.flush()
        return message

    def mark_context_window(self, *, chat_session_id: str, included_message_ids: list[str]) -> None:
        """标记哪些消息进入了最近上下文窗口。"""
        self.session.execute(
            update(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .values(budget_included=False, trimmed=True)
        )
        if included_message_ids:
            self.session.execute(
                update(ChatMessage)
                .where(ChatMessage.id.in_(included_message_ids))
                .values(budget_included=True, trimmed=False)
            )
        self.session.flush()
