from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.image_understanding_service import ImageUnderstandingService, ResolvedImageInput
from app.services.markdown_ingest_service import ImageDraft


def build_image_draft(source_url: str = "/uploads/tutorial/db-step.png") -> ImageDraft:
    """构造图片理解测试使用的图片草稿。"""
    return ImageDraft(
        source_url=source_url,
        normalized_url=source_url,
        alt_text="数据库配置截图",
        markdown_ref=f"![数据库配置截图]({source_url})",
        title_path="数据库教程 > 配置连接",
        section_id="section-001",
        image_index=0,
        neighbor_text_before="先打开数据库管理页面。",
        neighbor_text_after="然后检查端口和账号权限。",
        image_hash="image-hash-001",
    )


def test_image_understanding_uses_bailian_base_url_by_default():
    """未显式配置兼容地址时，应默认指向百炼 OpenAI 兼容接口。"""
    settings = Settings(openai_api_key="")

    assert settings.openai_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_image_understanding_resolves_relative_blog_image_url():
    """相对图片地址应能基于博客公开地址解析成绝对地址。"""
    service = ImageUnderstandingService(
        Settings(
            openai_api_key="",
            blog_public_base_url="https://blog.example.com",
        )
    )

    absolute_url = service._build_absolute_url("/uploads/tutorial/db-step.png")

    assert absolute_url == "https://blog.example.com/uploads/tutorial/db-step.png"


def test_image_understanding_builds_data_url_for_model(monkeypatch):
    """模型输入应把图片内容转换成 Data URL，避免私有仓库图片直连失败。"""
    service = ImageUnderstandingService(
        Settings(
            openai_api_key="",
            blog_public_base_url="https://blog.example.com",
        )
    )
    monkeypatch.setattr(service, "_fetch_image_bytes", lambda _: (b"fake-image-bytes", "image/png"))

    resolved = service._resolve_image_input(build_image_draft())

    assert resolved.source_url == "https://blog.example.com/uploads/tutorial/db-step.png"
    assert resolved.delivery_mode == "base64_data_url"
    assert resolved.input_url == "data:image/png;base64,ZmFrZS1pbWFnZS1ieXRlcw=="


def test_image_understanding_falls_back_without_api_key():
    """缺少百炼 Key 时，应生成可入库的回退图片特征。"""
    service = ImageUnderstandingService(Settings(openai_api_key=""))

    feature = service.describe_image(build_image_draft())

    assert feature.status == "fallback"
    assert feature.ocr_text is None
    assert feature.caption_text == "数据库配置截图"
    assert feature.caption_model == "mock-image-caption-local-v1"
    assert "先打开数据库管理页面" in (feature.feature_summary or "")
    assert "未配置百炼 API Key" in (feature.error_message or "")


def test_image_understanding_builds_ocr_image_message_with_pixel_limits():
    """OCR 图片消息应携带像素限制，便于控制模型处理成本。"""
    service = ImageUnderstandingService(
        Settings(
            openai_api_key="",
            image_ocr_min_pixels=1000,
            image_ocr_max_pixels=2000,
        )
    )
    resolved = ResolvedImageInput(
        input_url="data:image/png;base64,abc",
        delivery_mode="base64_data_url",
        source_url="https://blog.example.com/uploads/a.png",
        mime_type="image/png",
    )

    image_part = service._build_image_content_part(resolved, include_ocr_pixel_limits=True)

    assert image_part == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,abc"},
        "min_pixels": 1000,
        "max_pixels": 2000,
    }


@dataclass
class FakeTextPart:
    """模拟 SDK 可能返回的结构化文本片段。"""

    text: str


def test_image_understanding_normalizes_structured_model_text():
    """模型返回结构化片段时，应规整成纯文本。"""
    content = [
        {"text": "第一段"},
        FakeTextPart(text="第二段"),
        "第三段",
    ]

    normalized = ImageUnderstandingService._normalize_model_text(content)

    assert normalized == "第一段\n第二段\n第三段"
