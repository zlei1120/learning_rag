from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, generate_model_id

RAG_SCHEMA = Base.metadata.schema or "rag"


class ChatMessage(TimestampMixin, Base):
    """会话中的单条用户或助手消息。"""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_message", "chat_session_id", "message_index"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    chat_session_id: Mapped[str] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_summary: Mapped[str | None] = mapped_column(Text)
    source_payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    budget_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trimmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(Integer)

    chat_session: Mapped["ChatSession"] = relationship(back_populates="messages")
