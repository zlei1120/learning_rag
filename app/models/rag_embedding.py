from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, generate_model_id

RAG_SCHEMA = Base.metadata.schema or "rag"


class RagEmbedding(TimestampMixin, Base):
    """文本块向量表。"""

    __tablename__ = "rag_embeddings"
    __table_args__ = (
        Index("ix_rag_embeddings_chunk_id", "chunk_id"),
        Index("ix_rag_embeddings_model_version", "embedding_model", "embedding_version"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.rag_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    embedding_version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False)
    embedding_vector: Mapped[list[float] | None] = mapped_column(Vector(dim=None))

    chunk: Mapped["RagChunk"] = relationship(back_populates="embeddings")
