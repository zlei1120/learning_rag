from __future__ import annotations

from collections import OrderedDict

from app.schemas.common import RelatedImage, SourceItem
from app.services.retrieval_service import RetrievedChunk, RetrievedImage


def build_source_items(chunks: list[RetrievedChunk], *, include_sources: bool) -> list[SourceItem]:
    """把召回文本块按文章聚合成前端可展示的来源字段。"""
    if not include_sources:
        return []

    grouped_chunks: OrderedDict[str, dict[str, object]] = OrderedDict()

    for chunk in chunks:
        group_key = chunk.slug or chunk.title
        existing = grouped_chunks.get(group_key)

        if existing is None:
            grouped_chunks[group_key] = {
                "label": chunk.title,
                "slug": chunk.slug,
                "title_path": chunk.title_path,
                "match_count": 1,
            }
            continue

        existing["match_count"] = int(existing["match_count"]) + 1

        if not existing.get("title_path") and chunk.title_path:
            existing["title_path"] = chunk.title_path

    return [
        SourceItem(
            source_type="post",
            label=str(item["label"]),
            slug=item["slug"] if isinstance(item["slug"], str) else None,
            title_path=item["title_path"] if isinstance(item["title_path"], str) else None,
            match_count=int(item["match_count"]),
        )
        for item in grouped_chunks.values()
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
