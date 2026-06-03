from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(slots=True)
class BlogSourcePost:
    """博客真源文章在后端内部使用的结构。"""

    id: str
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
    updated_at: datetime


class BlogPostRepository:
    """从 geminiBlog 的 PostgreSQL 真源读取文章。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_post_by_id(self, post_id: str, *, include_unpublished: bool = False) -> BlogSourcePost | None:
        """按文章主键读取单篇博客。"""
        sql = """
        SELECT
            id,
            title,
            slug,
            content,
            excerpt,
            category,
            tags,
            published,
            date,
            series,
            "seriesOrder" AS series_order,
            "createdAt" AS created_at,
            "updatedAt" AS updated_at
        FROM "Post"
        WHERE id = :post_id
        """
        if not include_unpublished:
            sql += " AND published = TRUE"

        row = self.session.execute(text(sql), {"post_id": post_id}).mappings().first()
        return self._to_source_post(row) if row else None

    def get_post_by_slug(self, slug: str, *, include_unpublished: bool = False) -> BlogSourcePost | None:
        """按 slug 读取单篇博客。"""
        sql = """
        SELECT
            id,
            title,
            slug,
            content,
            excerpt,
            category,
            tags,
            published,
            date,
            series,
            "seriesOrder" AS series_order,
            "createdAt" AS created_at,
            "updatedAt" AS updated_at
        FROM "Post"
        WHERE slug = :slug
        """
        if not include_unpublished:
            sql += " AND published = TRUE"

        row = self.session.execute(text(sql), {"slug": slug}).mappings().first()
        return self._to_source_post(row) if row else None

    def list_posts_for_sync(
        self,
        *,
        include_unpublished: bool = False,
        updated_after: datetime | None = None,
        limit: int | None = None,
    ) -> list[BlogSourcePost]:
        """按更新时间顺序列出待同步文章。"""
        sql = """
        SELECT
            id,
            title,
            slug,
            content,
            excerpt,
            category,
            tags,
            published,
            date,
            series,
            "seriesOrder" AS series_order,
            "createdAt" AS created_at,
            "updatedAt" AS updated_at
        FROM "Post"
        WHERE 1 = 1
        """
        params: dict[str, object] = {}

        if not include_unpublished:
            sql += " AND published = TRUE"
        if updated_after is not None:
            sql += ' AND "updatedAt" >= :updated_after'
            params["updated_after"] = updated_after

        sql += ' ORDER BY "updatedAt" DESC, date DESC'
        if limit is not None:
            sql += " LIMIT :limit"
            params["limit"] = limit

        rows = self.session.execute(text(sql), params).mappings().all()
        return [self._to_source_post(row) for row in rows]

    @staticmethod
    def _to_source_post(row: dict[str, object]) -> BlogSourcePost:
        """把数据库行转换为内部文章对象。"""
        tags = row.get("tags")
        normalized_tags = [item for item in tags if isinstance(item, str) and item.strip()] if isinstance(tags, list) else []

        return BlogSourcePost(
            id=str(row["id"]),
            title=str(row["title"]),
            slug=str(row["slug"]),
            content=str(row["content"]),
            excerpt=str(row.get("excerpt") or ""),
            category=str(row.get("category") or ""),
            tags=normalized_tags,
            published=bool(row["published"]),
            date=row["date"],
            series=str(row.get("series") or ""),
            series_order=row.get("series_order"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
