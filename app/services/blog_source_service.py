from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from app.repositories.blog_post_repository import BlogSourcePost


@dataclass(slots=True)
class SourceDocument:
    """博客真源文章转换后的内部文档对象。"""

    source_post_id: str
    title: str
    slug: str
    content: str
    excerpt: str
    category: str
    tags: list[str]
    published: bool
    date: datetime
    series: str
    series_order: int | None
    created_at: datetime
    source_updated_at: datetime
    content_hash: str


class BlogSourceService:
    """负责把博客真源文章转换成 RAG 内部对象。"""

    def build_source_document(self, post: BlogSourcePost) -> SourceDocument:
        """把 `Post` 表记录转换成内部标准文档。"""
        content_hash = hashlib.sha256(post.content.encode("utf-8")).hexdigest()
        return SourceDocument(
            source_post_id=post.id,
            title=post.title,
            slug=post.slug,
            content=post.content,
            excerpt=post.excerpt,
            category=post.category,
            tags=post.tags,
            published=post.published,
            date=post.date,
            series=post.series,
            series_order=post.series_order,
            created_at=post.created_at,
            source_updated_at=post.updated_at,
            content_hash=content_hash,
        )
