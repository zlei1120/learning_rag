from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, generate_model_id

RAG_SCHEMA = Base.metadata.schema or "rag"


class RagChunk(TimestampMixin, Base):
    """文章切分后的文本块。"""

    __tablename__ = "rag_chunks"
    __table_args__ = (
        Index("ix_rag_chunks_document_chunk", "document_id", "chunk_index"),
        Index("ix_rag_chunks_section_id", "section_id"),
        Index("ix_rag_chunks_content_hash", "content_hash"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.rag_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[str | None] = mapped_column(String(128))
    title_path: Mapped[str | None] = mapped_column(String(512))
    section_title: Mapped[str | None] = mapped_column(String(255))
    heading_level: Mapped[int | None] = mapped_column(Integer)
    section_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    child_chunk_index: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(Integer)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    document: Mapped["RagDocument"] = relationship(back_populates="chunks")
    embeddings: Mapped[list["RagEmbedding"]] = relationship(back_populates="chunk", cascade="all, delete-orphan")
    image_links: Mapped[list["RagChunkImage"]] = relationship(back_populates="chunk", cascade="all, delete-orphan")
