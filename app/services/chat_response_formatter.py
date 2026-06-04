from __future__ import annotations

from app.schemas.common import RelatedImage, SourceItem
from app.services.retrieval_service import RetrievedChunk, RetrievedImage


def build_source_items(chunks: list[RetrievedChunk], *, include_sources: bool) -> list[SourceItem]:
    """把召回文本块转换为前端可展示的来源字段。"""
    if not include_sources:
        return []

    return [
        SourceItem(
            source_type="post_chunk",
            label=chunk.title,
            slug=chunk.slug,
            title_path=chunk.title_path,
            content_excerpt=_truncate_text(chunk.content, 220),
        )
        for chunk in chunks
    ]


def build_related_images(images: list[RetrievedImage], *, include_related_images: bool) -> list[RelatedImage]:
    """把召回图片特征转换为前端可展示的图片字段。"""
    if not include_related_images:
        return []

    return [
        RelatedImage(
            url=image.url,
            alt_text=image.alt_text,
            caption=image.caption or image.feature_summary,
            source_slug=image.slug,
            title_path=image.title_path,
        )
        for image in images
    ]


def _truncate_text(value: str, max_length: int) -> str:
    """压缩来源片段，避免接口响应过长。"""
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length].rstrip()}..."
