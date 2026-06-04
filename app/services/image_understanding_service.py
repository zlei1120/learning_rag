from __future__ import annotations

import base64
import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.services.markdown_ingest_service import ImageDraft

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


@dataclass(slots=True)
class ImageFeatureDraft:
    """待写入数据库的图片文本特征。"""

    ocr_text: str | None
    ocr_text_summary: str | None
    caption_text: str | None
    feature_summary: str | None
    ocr_model: str | None
    caption_model: str | None
    feature_hash: str
    status: str
    error_message: str | None
    token_estimate: int


@dataclass(slots=True)
class ResolvedImageInput:
    """提供给多模态模型的图片输入。"""

    input_url: str
    delivery_mode: str
    source_url: str
    mime_type: str | None = None


class ImageUnderstandingService:
    """封装图片 OCR / caption 能力，优先走百炼官方兼容接口。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = self._create_client()

    def describe_images(self, image_drafts: list[ImageDraft]) -> list[ImageFeatureDraft]:
        """批量生成图片特征。"""
        return [self.describe_image(image) for image in image_drafts]

    def describe_image(self, image: ImageDraft) -> ImageFeatureDraft:
        """优先调用百炼模型，失败时回退到可运行的启发式说明。"""
        if self.client is None:
            return self._build_fallback_feature(image, reason="未配置百炼 API Key，使用本地回退说明。")

        try:
            resolved_input = self._resolve_image_input(image)
            ocr_text = self._extract_ocr_text(resolved_input)
            caption_text = self._generate_caption(resolved_input)
            return self._build_model_feature(
                image=image,
                ocr_text=ocr_text,
                caption_text=caption_text,
                delivery_mode=resolved_input.delivery_mode,
            )
        except Exception as exc:
            return self._build_fallback_feature(image, reason=f"百炼图片理解调用失败：{exc}")

    def _create_client(self) -> OpenAI | None:
        """初始化百炼兼容的 OpenAI 客户端。"""
        if OpenAI is None or not self.settings.openai_api_key:
            return None

        return OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )

    def _resolve_image_input(self, image: ImageDraft) -> ResolvedImageInput:
        """把文章中的图片地址解析成模型可直接消费的输入。"""
        absolute_url = self._build_absolute_url(image.source_url)
        if absolute_url is None:
            raise ValueError("图片地址不是绝对路径，且未配置 BLOG_PUBLIC_BASE_URL。")

        image_bytes, mime_type = self._fetch_image_bytes(absolute_url)
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        return ResolvedImageInput(
            input_url=data_url,
            delivery_mode="base64_data_url",
            source_url=absolute_url,
            mime_type=mime_type,
        )

    def _build_absolute_url(self, source_url: str) -> str | None:
        """解析图片地址，兼容相对路径上传资源。"""
        normalized = source_url.strip()
        parsed = urlparse(normalized)
        if parsed.scheme in {"http", "https"}:
            return normalized

        if self.settings.blog_public_base_url:
            return urljoin(self.settings.blog_public_base_url.rstrip("/") + "/", normalized.lstrip("/"))

        return None

    def _fetch_image_bytes(self, absolute_url: str) -> tuple[bytes, str]:
        """下载图片内容，便于传给支持 Data URL 的模型。"""
        request = Request(
            absolute_url,
            headers={
                "User-Agent": "learning-rag-image-understanding/1.0",
                "Accept": "image/*",
            },
        )
        with urlopen(request, timeout=self.settings.image_fetch_timeout_seconds) as response:
            image_bytes = response.read()
            mime_type = response.headers.get_content_type()

        if not mime_type or mime_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(absolute_url)
            mime_type = guessed or "image/png"

        return image_bytes, mime_type

    def _extract_ocr_text(self, resolved_input: ResolvedImageInput) -> str | None:
        """调用百炼 OCR 模型提取图片文字。"""
        completion = self.client.chat.completions.create(
            model=self.settings.ocr_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        self._build_image_content_part(resolved_input, include_ocr_pixel_limits=True),
                        {
                            "type": "text",
                            "text": "请只提取图像中清晰可见的文字内容，不要添加额外解释、标题或 Markdown 格式；如果图中基本没有可读文字，返回空字符串。",
                        },
                    ],
                }
            ],
        )
        return self._normalize_model_text(completion.choices[0].message.content)

    def _generate_caption(self, resolved_input: ResolvedImageInput) -> str | None:
        """调用百炼视觉模型生成面向教程场景的图片说明。"""
        completion = self.client.chat.completions.create(
            model=self.settings.image_caption_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        self._build_image_content_part(resolved_input),
                        {
                            "type": "text",
                            "text": "请用中文概括这张博客配图的关键信息，重点说明界面元素、步骤指示、按钮、表格、代码片段或流程提示。控制在 1 到 2 句，不要编造看不清的细节。",
                        },
                    ],
                }
            ],
        )
        return self._normalize_model_text(completion.choices[0].message.content)

    def _build_image_content_part(
        self,
        resolved_input: ResolvedImageInput,
        *,
        include_ocr_pixel_limits: bool = False,
    ) -> dict[str, object]:
        """构造兼容百炼 OpenAI 模式的图片消息片段。"""
        image_part: dict[str, object] = {
            "type": "image_url",
            "image_url": {"url": resolved_input.input_url},
        }
        if include_ocr_pixel_limits:
            image_part["min_pixels"] = self.settings.image_ocr_min_pixels
            image_part["max_pixels"] = self.settings.image_ocr_max_pixels
        return image_part

    @staticmethod
    def _normalize_model_text(content: str | list[object] | None) -> str | None:
        """把模型返回内容规整成纯文本。"""
        if content is None:
            return None
        if isinstance(content, str):
            normalized = content.strip()
            return normalized or None

        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    text_parts.append(item.strip())
                continue
            if isinstance(item, dict):
                candidate = item.get("text") if isinstance(item.get("text"), str) else None
                if candidate and candidate.strip():
                    text_parts.append(candidate.strip())
                continue

            candidate = getattr(item, "text", None)
            if isinstance(candidate, str) and candidate.strip():
                text_parts.append(candidate.strip())

        combined = "\n".join(text_parts).strip()
        return combined or None

    def _build_model_feature(
        self,
        *,
        image: ImageDraft,
        ocr_text: str | None,
        caption_text: str | None,
        delivery_mode: str,
    ) -> ImageFeatureDraft:
        """将 OCR 和视觉说明结果组装成统一特征。"""
        ocr_text_summary = self._truncate_text(ocr_text, 220)
        feature_summary_parts = []
        if caption_text:
            feature_summary_parts.append(caption_text)
        if ocr_text_summary:
            feature_summary_parts.append(f"图中文字摘要：{ocr_text_summary}")
        if image.title_path:
            feature_summary_parts.append(f"所在章节：{image.title_path}")
        feature_summary_parts.append(f"输入方式：{delivery_mode}")
        feature_summary = "；".join(feature_summary_parts)

        hash_source = f"{image.image_hash}|{ocr_text or ''}|{caption_text or ''}|{feature_summary}"
        return ImageFeatureDraft(
            ocr_text=ocr_text,
            ocr_text_summary=ocr_text_summary,
            caption_text=caption_text,
            feature_summary=feature_summary,
            ocr_model=self.settings.ocr_model,
            caption_model=self.settings.image_caption_model,
            feature_hash=hashlib.sha256(hash_source.encode("utf-8")).hexdigest(),
            status="succeeded",
            error_message=None,
            token_estimate=max(1, len((ocr_text or "") + (caption_text or "") + feature_summary) // 4),
        )

    def _build_fallback_feature(self, image: ImageDraft, *, reason: str) -> ImageFeatureDraft:
        """在无法调用模型时，用启发式信息生成可运行的图片特征。"""
        file_name = PurePosixPath(image.normalized_url or image.source_url).name or "未命名图片"
        readable_name = file_name.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()
        caption = image.alt_text or readable_name or "文章配图"

        context_parts = [part for part in [image.alt_text, image.neighbor_text_before, image.neighbor_text_after] if part]
        context_summary = " ".join(context_parts).strip() or None
        feature_summary = f"{caption}；所在位置：{image.title_path}"
        if context_summary:
            feature_summary = f"{feature_summary}；上下文：{context_summary[:200]}"
        feature_summary = f"{feature_summary}；回退原因：{reason}"

        hash_source = f"{image.image_hash}|{caption}|{context_summary or ''}|{feature_summary}"
        return ImageFeatureDraft(
            ocr_text=None,
            ocr_text_summary=context_summary,
            caption_text=caption,
            feature_summary=feature_summary,
            ocr_model=self.settings.ocr_model if self.settings.openai_api_key else None,
            caption_model=self.settings.image_caption_model if self.settings.openai_api_key else "mock-image-caption-local-v1",
            feature_hash=hashlib.sha256(hash_source.encode("utf-8")).hexdigest(),
            status="fallback",
            error_message=reason,
            token_estimate=max(1, len((context_summary or "") + feature_summary) // 4),
        )

    @staticmethod
    def _truncate_text(text: str | None, max_length: int) -> str | None:
        """截断过长 OCR 文本，避免后续上下文爆炸。"""
        if text is None:
            return None
        normalized = " ".join(text.split())
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[:max_length].rstrip()}..."
