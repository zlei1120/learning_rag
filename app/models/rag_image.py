from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, generate_model_id

RAG_SCHEMA = Base.metadata.schema or "rag"


class RagImage(TimestampMixin, Base):
    """文章中的图片引用与上下文信息。"""

    __tablename__ = "rag_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.rag_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    alt_text: Mapped[str | None] = mapped_column(Text)
    markdown_ref: Mapped[str | None] = mapped_column(Text)
    title_path: Mapped[str | None] = mapped_column(String(512))
    section_id: Mapped[str | None] = mapped_column(String(128))
    image_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neighbor_text_before: Mapped[str | None] = mapped_column(Text)
    neighbor_text_after: Mapped[str | None] = mapped_column(Text)
    image_hash: Mapped[str | None] = mapped_column(String(64))

    document: Mapped["RagDocument"] = relationship(back_populates="images")
    features: Mapped[list["RagImageFeature"]] = relationship(back_populates="image", cascade="all, delete-orphan")
    chunk_links: Mapped[list["RagChunkImage"]] = relationship(back_populates="image", cascade="all, delete-orphan")


class RagImageFeature(TimestampMixin, Base):
    """图片 OCR、说明与压缩后文本特征。"""

    __tablename__ = "rag_image_features"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    image_id: Mapped[str] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.rag_images.id", ondelete="CASCADE"),
        nullable=False,
    )
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_text_summary: Mapped[str | None] = mapped_column(Text)
    caption_text: Mapped[str | None] = mapped_column(Text)
    feature_summary: Mapped[str | None] = mapped_column(Text)
    ocr_model: Mapped[str | None] = mapped_column(String(128))
    caption_model: Mapped[str | None] = mapped_column(String(128))
    feature_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    token_estimate: Mapped[int | None] = mapped_column(Integer)

    image: Mapped["RagImage"] = relationship(back_populates="features")


class RagChunkImage(TimestampMixin, Base):
    """文本块与图片之间的关联关系。"""

    __tablename__ = "rag_chunk_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_model_id)
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.rag_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_id: Mapped[str] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.rag_images.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    distance_score: Mapped[float | None] = mapped_column(Float)

    chunk: Mapped["RagChunk"] = relationship(back_populates="image_links")
    image: Mapped["RagImage"] = relationship(back_populates="chunk_links")
