from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, generate_model_id

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession

RAG_SCHEMA = Base.metadata.schema or "rag"


class MemoryRecord(TimestampMixin, Base):
    """会话摘要记忆和后续扩展记忆。"""

    __tablename__ = "memory_records"
    __table_args__ = (
        Index("ix_memory_records_session_scope", "chat_session_id", "memory_scope", "memory_type"),
        Index("ix_memory_records_content_hash", "content_hash"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    chat_session_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.chat_sessions.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_key: Mapped[str | None] = mapped_column(String(128))
    memory_scope: Mapped[str] = mapped_column(String(32), default="session", nullable=False)
    memory_type: Mapped[str] = mapped_column(String(32), default="summary", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    importance_score: Mapped[float | None] = mapped_column(Float)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chat_session: Mapped["ChatSession"] = relationship(back_populates="memories")
