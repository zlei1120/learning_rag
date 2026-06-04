from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, generate_model_id


class ChatSession(TimestampMixin, Base):
    """多轮问答的会话线程。"""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_key: Mapped[str | None] = mapped_column(String(128))
    session_scope: Mapped[str] = mapped_column(String(32), default="anonymous", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checkpoint_ref: Mapped[str | None] = mapped_column(String(255))

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="chat_session", cascade="all, delete-orphan")
    memories: Mapped[list["MemoryRecord"]] = relationship(back_populates="chat_session", cascade="all, delete-orphan")
