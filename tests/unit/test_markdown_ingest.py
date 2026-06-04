from __future__ import annotations

from app.core.config import Settings
from app.services.markdown_ingest_service import MarkdownIngestService


def test_markdown_ingest_extracts_chunks_and_images():
    """Markdown 解析应同时产出文本块和图片草稿。"""
    service = MarkdownIngestService(
        Settings(
            ingest_chunk_size=80,
            ingest_chunk_overlap=10,
            ingest_image_context_window=40,
        )
    )
    content = """
## 数据库配置
先准备 PostgreSQL 服务，并检查端口是否开放。

![数据库结构图](https://example.com/assets/db-setup.png)

然后执行迁移脚本，确认表结构已经创建完成。

### 第二步
检查连接串和账号权限，避免后续同步失败。
""".strip()

    result = service.parse(
        slug="db-guide",
        title="数据库教程",
        content=content,
    )

    assert len(result.chunks) >= 2
    assert any("标题路径：" in chunk.content for chunk in result.chunks)
    assert any("数据库配置" in chunk.title_path for chunk in result.chunks)

    assert len(result.images) == 1
    image = result.images[0]
    assert image.source_url == "https://example.com/assets/db-setup.png"
    assert image.normalized_url == "https://example.com/assets/db-setup.png"
    assert image.alt_text == "数据库结构图"
    assert "PostgreSQL" in (image.neighbor_text_before or "")
    assert "迁移脚本" in (image.neighbor_text_after or "")


def test_markdown_ingest_falls_back_for_plain_text_article():
    """没有 Markdown 标题时，也应保留至少一个 section 和 chunk。"""
    service = MarkdownIngestService(Settings())

    result = service.parse(
        slug="plain-post",
        title="普通文章",
        content="这是一篇没有标题层级的文章，但也应该能正常切分。",
    )

    assert len(result.chunks) == 1
    assert result.chunks[0].title_path == "普通文章"
    assert result.images == []
