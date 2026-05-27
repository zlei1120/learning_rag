import hashlib
from dataclasses import dataclass
from typing import Callable, List

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter


@dataclass
class MarkdownSection:
    """Markdown 标题切分后的章节块。"""

    title_path: str
    section_title: str
    heading_level: int
    section_index: int
    content: str


class MarkdownChunker:
    """
    Markdown 专用切分器。

    Markdown 和普通纯文本不一样，它的 `# / ## / ###` 标题本身就是天然的父级上下文。
    标题解析交给 LangChain 的 MarkdownHeaderTextSplitter 处理
    这里主要负责标题路径增强和语义二次切分。
    """

    def __init__(
        self,
        semantic_split_text: Callable[[str], List[str]],
        max_chunk_size: int,
    ) -> None:
        """
        Args:
            semantic_split_text: 复用现有语义切分函数，避免在 MarkdownChunker 里重复造轮子。
            max_chunk_size: section 超过该长度时，再做语义二次切分。
        """
        self.semantic_split_text = semantic_split_text
        self.max_chunk_size = max_chunk_size
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
                ("####", "h4"),
                ("#####", "h5"),
                ("######", "h6"),
            ],
            strip_headers=False,
        )

    def split_document(self, document: Document) -> List[Document]:
        """把单个 Markdown 文档切成带标题上下文的 chunk。"""
        sections = self._split_sections(document.page_content)
        if not sections:
            return []

        chunks: List[Document] = []
        global_chunk_index = 0
        for section in sections:
            section_chunks = self._split_section_content(section.content)
            section_id = self._build_section_id(document, section)
            for child_chunk_index, chunk_text in enumerate(section_chunks):
                metadata = dict(document.metadata)
                metadata.update(
                    {
                        "title_path": section.title_path,
                        "section_title": section.section_title,
                        "heading_level": section.heading_level,
                        "section_index": section.section_index,
                        "section_id": section_id,
                        "child_chunk_index": child_chunk_index,
                        "chunk_index": global_chunk_index,
                    }
                )

                page_content = self._build_chunk_content(section.title_path, chunk_text)
                metadata["chunk_size"] = len(page_content)
                chunks.append(Document(page_content=page_content, metadata=metadata))
                global_chunk_index += 1

        return chunks

    def _split_sections(self, text: str) -> List[MarkdownSection]:
        """用 LangChain 按 Markdown 标题切 section，并计算统一的标题路径。"""
        sections: List[MarkdownSection] = []
        header_docs = self.header_splitter.split_text(text)

        for section_index, header_doc in enumerate(header_docs):
            content = header_doc.page_content.strip()
            if not content:
                continue

            # MarkdownHeaderTextSplitter 会把命中的标题层级放到 metadata，
            # 例如 {"h1": "宫保鸡丁的做法", "h2": "计算"}。
            # 我们把它转成统一的 title_path，方便检索、重排和 prompt 展示。
            title_items = [
                (int(key[1:]), value)
                for key, value in header_doc.metadata.items()
                if key.startswith("h") and key[1:].isdigit()
            ]
            title_items.sort(key=lambda item: item[0])
            title_path_parts = [title for _, title in title_items]
            title_path = " > ".join(title_path_parts) if title_path_parts else "无标题"
            heading_level = title_items[-1][0] if title_items else 0
            section_title = title_path_parts[-1] if title_path_parts else "无标题"

            sections.append(
                MarkdownSection(
                    title_path=title_path,
                    section_title=section_title,
                    heading_level=heading_level,
                    section_index=section_index,
                    content=content,
                )
            )
        return sections

    def _split_section_content(self, content: str) -> List[str]:
        """section 内部太长时再语义切分，短 section 保持完整。"""
        if len(content) <= self.max_chunk_size:
            return [content]

        # 标题切分负责保留 Markdown 结构，语义切分负责控制 chunk 大小。
        # 这样既不会把大章节整个塞进向量库，也不容易把列表项切成没上下文的孤儿句。
        return self.semantic_split_text(content)

    def _build_chunk_content(self, title_path: str, chunk_text: str) -> str:
        """把标题路径写进 page_content，让 embedding、BM25、reranker 都能看到结构信息。"""
        # 短 chunk 单独看语义很弱，比如“莴笋 = 约 250g”。
        # 加上标题路径后，它就变成“宫保鸡丁 > 计算”下面的用量信息，相关性会稳定很多。
        return f"标题路径：{title_path}\n内容：\n{chunk_text.strip()}"

    def _build_section_id(self, document: Document, section: MarkdownSection) -> str:
        """生成同一 section 的稳定标识，后续可用于同 section 父子扩展。"""
        source = document.metadata.get("source_file") or document.metadata.get("file_name", "")
        raw_key = f"{source}|{section.section_index}|{section.title_path}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()
