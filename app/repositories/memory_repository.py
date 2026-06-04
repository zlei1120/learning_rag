from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.memory_record import MemoryRecord


class MemoryRepository:
    """管理会话摘要记忆。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_session_summary(self, chat_session_id: str) -> MemoryRecord | None:
        """读取当前会话最新的摘要记忆。"""
        statement = (
            select(MemoryRecord)
            .where(MemoryRecord.chat_session_id == chat_session_id)
            .where(MemoryRecord.memory_scope == "session")
            .where(MemoryRecord.memory_type == "summary")
            .order_by(MemoryRecord.updated_at.desc(), MemoryRecord.created_at.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_session_summary(
        self,
        *,
        chat_session_id: str,
        user_key: str | None,
        content: str,
        content_hash: str,
        importance_score: float | None = 0.8,
    ) -> MemoryRecord:
        """写入或更新会话摘要记忆。"""
        record = self.get_latest_session_summary(chat_session_id)
        if record is None:
            record = MemoryRecord(
                chat_session_id=chat_session_id,
                user_key=user_key,
                memory_scope="session",
                memory_type="summary",
                content=content,
                content_hash=content_hash,
                importance_score=importance_score,
            )
            self.session.add(record)
        else:
            record.user_key = user_key
            record.content = content
            record.content_hash = content_hash
            record.importance_score = importance_score

        self.session.flush()
        return record

    def delete_session_summary(self, chat_session_id: str) -> None:
        """删除当前会话已有的摘要记忆。"""
        self.session.execute(
            delete(MemoryRecord)
            .where(MemoryRecord.chat_session_id == chat_session_id)
            .where(MemoryRecord.memory_scope == "session")
            .where(MemoryRecord.memory_type == "summary")
        )
        self.session.flush()
