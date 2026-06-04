from __future__ import annotations

from app.services.chat_response_formatter import build_related_images, build_source_items
from app.services.retrieval_service import RetrievedChunk, RetrievedImage


def test_chat_response_formatter_builds_source_items():
    """来源结构应包含前端展示所需的文章、slug、标题路径和片段。"""
    chunks = [
        RetrievedChunk(
            chunk_id="chunk-001",
            document_id="doc-001",
            slug="db-guide",
            title="数据库教程",
            title_path="数据库教程 > 准备数据库",
            content="标题路径：数据库教程 > 准备数据库\n内容：\n先打开数据库管理页面，确认 PostgreSQL 服务已经启动。",
            token_estimate=20,
            score=0.9,
        )
    ]

    sources = build_source_items(chunks, include_sources=True)

    assert len(sources) == 1
    assert sources[0].source_type == "post_chunk"
    assert sources[0].label == "数据库教程"
    assert sources[0].slug == "db-guide"
    assert sources[0].title_path == "数据库教程 > 准备数据库"
    assert "PostgreSQL" in (sources[0].content_excerpt or "")


def test_chat_response_formatter_respects_source_switch():
    """前端关闭来源返回时，应返回空来源列表。"""
    sources = build_source_items([], include_sources=False)

    assert sources == []


def test_chat_response_formatter_builds_related_images():
    """相关图片结构应包含图片地址、说明、来源文章和标题路径。"""
    images = [
        RetrievedImage(
            image_id="image-001",
            document_id="doc-001",
            slug="db-guide",
            title="数据库教程",
            url="/uploads/tutorial/db-step.png",
            alt_text="数据库配置截图",
            title_path="数据库教程 > 准备数据库",
            caption="数据库配置截图展示端口和账号权限检查。",
            feature_summary="图片文字摘要：5432",
            score=0.8,
        )
    ]

    related_images = build_related_images(images, include_related_images=True)

    assert len(related_images) == 1
    assert related_images[0].url == "/uploads/tutorial/db-step.png"
    assert related_images[0].alt_text == "数据库配置截图"
    assert related_images[0].caption == "数据库配置截图展示端口和账号权限检查。"
    assert related_images[0].source_slug == "db-guide"
    assert related_images[0].title_path == "数据库教程 > 准备数据库"


def test_chat_response_formatter_respects_image_switch():
    """前端关闭图片返回时，应返回空图片列表。"""
    related_images = build_related_images([], include_related_images=False)

    assert related_images == []
