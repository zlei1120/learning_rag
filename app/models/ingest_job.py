from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, generate_model_id


class IngestJob(TimestampMixin, Base):
    """文章同步与重建任务记录。"""

    __tablename__ = "rag_ingest_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_post_id: Mapped[str | None] = mapped_column(String(64))
    target_slug: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(64), default="api", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
