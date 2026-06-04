from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag_document import RagDocument

if TYPE_CHECKING:
    from app.services.blog_source_service import SourceDocument


class RagDocumentRepository:
    """管理 RAG 侧文章主索引记录。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_source_post_id(self, source_post_id: str) -> RagDocument | None:
        """按博客真源主键查找已同步文档。"""
        statement = select(RagDocument).where(RagDocument.source_post_id == source_post_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> RagDocument | None:
        """按 slug 查找已同步文档。"""
        statement = select(RagDocument).where(RagDocument.slug == slug)
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_from_source(self, source_document: SourceDocument) -> RagDocument:
        """把博客真源的元数据写入或更新到 RAG 文档表。"""
        document = self.get_by_source_post_id(source_document.source_post_id)
        now = datetime.now(timezone.utc)

        if document is None:
            document = RagDocument(
                source_post_id=source_document.source_post_id,
                slug=source_document.slug,
                title=source_document.title,
                published=source_document.published,
                source_updated_at=source_document.source_updated_at,
                content_hash=source_document.content_hash,
                excerpt=source_document.excerpt,
                category=source_document.category,
                tags_json=source_document.tags,
                series=source_document.series,
                series_order=source_document.series_order,
                last_synced_at=now,
                sync_status="running",
            )
            self.session.add(document)
        else:
            document.slug = source_document.slug
            document.title = source_document.title
            document.published = source_document.published
            document.source_updated_at = source_document.source_updated_at
            document.content_hash = source_document.content_hash
            document.excerpt = source_document.excerpt
            document.category = source_document.category
            document.tags_json = source_document.tags
            document.series = source_document.series
            document.series_order = source_document.series_order
            document.last_synced_at = now
            document.sync_status = "running"

        self.session.flush()
        return document

    def mark_succeeded(self, document: RagDocument) -> RagDocument:
        """标记文档已同步成功。"""
        document.last_synced_at = datetime.now(timezone.utc)
        document.sync_status = "succeeded"
        self.session.flush()
        return document

    def mark_failed(self, document: RagDocument | None) -> None:
        """标记文档同步失败。"""
        if document is None:
            return

        document.sync_status = "failed"
        document.last_synced_at = datetime.now(timezone.utc)
        self.session.flush()
