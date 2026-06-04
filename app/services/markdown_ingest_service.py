from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.core.config import Settings, get_settings

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)")


@dataclass(slots=True)
class SectionDraft:
    """Markdown 标题切分后的章节结构。"""

    title_path: str
    section_title: str
    heading_level: int
    section_index: int
    section_id: str
    content: str


@dataclass(slots=True)
class ChunkDraft:
    """待写入数据库的文本块。"""

    section_id: str
    title_path: str
    section_title: str
    heading_level: int
    section_index: int
    chunk_index: int
    child_chunk_index: int
    content: str
    content_hash: str
    token_estimate: int
    has_images: bool


@dataclass(slots=True)
class ImageDraft:
    """待写入数据库的图片引用。"""

    source_url: str
    normalized_url: str
    alt_text: str | None
    markdown_ref: str
    title_path: str
    section_id: str
    image_index: int
    neighbor_text_before: str | None
    neighbor_text_after: str | None
    image_hash: str


@dataclass(slots=True)
class MarkdownIngestResult:
    """Markdown 解析后的图文结果。"""

    chunks: list[ChunkDraft]
    images: list[ImageDraft]


class MarkdownIngestService:
    """负责 Markdown 文章的切分与图片抽取。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def parse(self, *, slug: str, title: str, content: str) -> MarkdownIngestResult:
        """把博客正文解析成 chunk 和图片草稿。"""
        sections = self._split_sections(slug=slug, title=title, content=content)

        chunks: list[ChunkDraft] = []
        images: list[ImageDraft] = []
        global_chunk_index = 0
        global_image_index = 0

        for section in sections:
            section_images = self._extract_images(section)
            images.extend(section_images)

            chunk_texts = self._split_text(section.content)
            if not chunk_texts and section.content.strip():
                chunk_texts = [section.content.strip()]

            for child_chunk_index, chunk_text in enumerate(chunk_texts):
                normalized_text = chunk_text.strip()
                if not normalized_text:
                    continue

                chunk_has_images = any(image.section_id == section.section_id for image in section_images)
                chunk_content = self._build_chunk_content(section.title_path, normalized_text)
                chunks.append(
                    ChunkDraft(
                        section_id=section.section_id,
                        title_path=section.title_path,
                        section_title=section.section_title,
                        heading_level=section.heading_level,
                        section_index=section.section_index,
                        chunk_index=global_chunk_index,
                        child_chunk_index=child_chunk_index,
                        content=chunk_content,
                        content_hash=self._hash_text(chunk_content),
                        token_estimate=self._estimate_tokens(chunk_content),
                        has_images=chunk_has_images,
                    )
                )
                global_chunk_index += 1

            for image in section_images:
                image.image_index = global_image_index
                global_image_index += 1

        return MarkdownIngestResult(chunks=chunks, images=images)

    def _split_sections(self, *, slug: str, title: str, content: str) -> list[SectionDraft]:
        """按 Markdown 标题切分章节。"""
        lines = content.splitlines()
        sections: list[SectionDraft] = []
        heading_stack: list[tuple[int, str]] = [(1, title)]
        buffer: list[str] = []
        section_index = 0

        def flush_section() -> None:
            nonlocal buffer, section_index
            section_content = "\n".join(buffer).strip()
            if not section_content:
                buffer = []
                return

            title_path = " > ".join(item[1] for item in heading_stack if item[1].strip())
            section_title = heading_stack[-1][1] if heading_stack else title
            heading_level = heading_stack[-1][0] if heading_stack else 1
            raw_section_key = f"{slug}|{section_index}|{title_path}"
            section_id = hashlib.md5(raw_section_key.encode("utf-8")).hexdigest()
            sections.append(
                SectionDraft(
                    title_path=title_path,
                    section_title=section_title,
                    heading_level=heading_level,
                    section_index=section_index,
                    section_id=section_id,
                    content=section_content,
                )
            )
            section_index += 1
            buffer = []

        for line in lines:
            matched = HEADING_PATTERN.match(line.strip())
            if matched:
                flush_section()
                level = len(matched.group(1))
                heading_text = matched.group(2).strip() or "无标题"
                heading_stack = [item for item in heading_stack if item[0] < level]
                heading_stack.append((level, heading_text))
                continue

            buffer.append(line)

        flush_section()

        if not sections and content.strip():
            raw_section_key = f"{slug}|0|{title}"
            sections.append(
                SectionDraft(
                    title_path=title,
                    section_title=title,
                    heading_level=1,
                    section_index=0,
                    section_id=hashlib.md5(raw_section_key.encode("utf-8")).hexdigest(),
                    content=content.strip(),
                )
            )

        return sections

    def _split_text(self, content: str) -> list[str]:
        """按窗口大小切分章节文本，同时尽量照顾段落边界。"""
        normalized = content.strip()
        if not normalized:
            return []

        chunk_size = self.settings.ingest_chunk_size
        overlap = self.settings.ingest_chunk_overlap
        chunks: list[str] = []
        start = 0

        while start < len(normalized):
            target_end = min(start + chunk_size, len(normalized))
            end = self._find_split_boundary(normalized, start, target_end)
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - overlap, start + 1)

        return chunks

    @staticmethod
    def _find_split_boundary(text: str, start: int, target_end: int) -> int:
        """优先在自然边界处分块，避免把段落切得过碎。"""
        if target_end >= len(text):
            return len(text)

        boundary_chars = "\n。！？；.!?;"
        search_window = text[start:target_end]
        best_boundary = max(search_window.rfind(char) for char in boundary_chars)
        if best_boundary >= int(len(search_window) * 0.6):
            return start + best_boundary + 1
        return target_end

    def _extract_images(self, section: SectionDraft) -> list[ImageDraft]:
        """提取章节中的 Markdown 图片。"""
        images: list[ImageDraft] = []
        for match in IMAGE_PATTERN.finditer(section.content):
            source_url = match.group("url").strip()
            markdown_ref = match.group(0)
            alt_text = match.group("alt").strip() or None
            before_start = max(0, match.start() - self.settings.ingest_image_context_window)
            after_end = min(len(section.content), match.end() + self.settings.ingest_image_context_window)
            neighbor_text_before = section.content[before_start:match.start()].strip() or None
            neighbor_text_after = section.content[match.end():after_end].strip() or None
            image_hash = self._hash_text(f"{section.section_id}|{source_url}|{markdown_ref}")

            images.append(
                ImageDraft(
                    source_url=source_url,
                    normalized_url=self._normalize_url(source_url),
                    alt_text=alt_text,
                    markdown_ref=markdown_ref,
                    title_path=section.title_path,
                    section_id=section.section_id,
                    image_index=0,
                    neighbor_text_before=neighbor_text_before,
                    neighbor_text_after=neighbor_text_after,
                    image_hash=image_hash,
                )
            )

        return images

    @staticmethod
    def _normalize_url(source_url: str) -> str:
        """规范化图片地址，方便做去重。"""
        parts = urlsplit(source_url.strip())
        normalized_path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), normalized_path, "", ""))

    @staticmethod
    def _build_chunk_content(title_path: str, content: str) -> str:
        """把标题路径拼回文本块，便于后续检索和解释。"""
        return f"标题路径：{title_path}\n内容：\n{content}"

    @staticmethod
    def _hash_text(value: str) -> str:
        """生成稳定哈希。"""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _estimate_tokens(value: str) -> int:
        """用字符长度做一个保守 token 估算。"""
        return max(1, len(value) // 4)
