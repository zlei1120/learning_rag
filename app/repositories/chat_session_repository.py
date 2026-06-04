from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession


class ChatSessionRepository:
    """管理多轮会话线程。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, session_row_id: str) -> ChatSession | None:
        """按数据库主键读取会话。"""
        statement = select(ChatSession).where(ChatSession.id == session_row_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_public_session_id(self, session_id: str) -> ChatSession | None:
        """按对外 `session_id` 读取会话。"""
        statement = select(ChatSession).where(ChatSession.session_id == session_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_or_create(self, *, session_id: str, user_key: str | None = None) -> ChatSession:
        """读取已有会话，不存在时自动创建。"""
        chat_session = self.get_by_public_session_id(session_id)
        if chat_session is None:
            chat_session = ChatSession(
                session_id=session_id,
                user_key=user_key,
                session_scope="user" if user_key else "anonymous",
                status="active",
            )
            self.session.add(chat_session)
            self.session.flush()
            return chat_session

        if user_key and chat_session.user_key != user_key:
            chat_session.user_key = user_key
            chat_session.session_scope = "user"

        self.session.flush()
        return chat_session

    def touch(self, chat_session: ChatSession, *, checkpoint_ref: str | None = None) -> ChatSession:
        """更新会话最近活跃时间和最近检查点引用。"""
        chat_session.last_message_at = datetime.now(timezone.utc)
        if checkpoint_ref:
            chat_session.last_checkpoint_ref = checkpoint_ref
        self.session.flush()
        return chat_session

    def update_summary(self, chat_session: ChatSession, summary_text: str | None) -> ChatSession:
        """更新会话摘要字段。"""
        chat_session.summary_text = summary_text
        self.session.flush()
        return chat_session
