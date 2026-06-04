import re
from pathlib import Path
from typing import List

from langchain_core.documents import Document


class ChunkSaver:
    """保存分割出来的chunk，供后续的人工检查和调试使用
    """
    def __init__(
        self,
        chunks_dir: str | Path,
        markdown_prefix: str,
        markdown_title: str = "Chunk",
    ) -> None:
        """
     
        """
        self.chunks_dir = Path(chunks_dir)
        self.markdown_prefix = markdown_prefix
        self.markdown_title = markdown_title
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    def save_chunks(self, documents: List[Document]) -> None:
        """
        保存 chunk 列表。
        """
        # 每次重新切分前，先清理同前缀的旧调试文件。
        for old_file in self.chunks_dir.glob(f"{self.markdown_prefix}_*.md"):
            old_file.unlink()

        chunks_data = []
        for idx, doc in enumerate(documents):
            chunks_data.append(
                {
                    "chunk_index": idx,
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                }
            )
            self._save_single_chunk(doc, idx)

   
    def _save_single_chunk(self, chunk: Document, index: int) -> None:
        """
        把单个 chunk 保存成 Markdown 文件。
        这个文件主要是给人看的，不参与程序读取逻辑。
        """
        source = chunk.metadata.get("file_name") or chunk.metadata.get("source") or "unknown"
        content = f"""# {self.markdown_title} {index}
## 元数据
- **来源文件**: {source}
- **字符数**: {len(chunk.page_content)}
- **分块索引**: {chunk.metadata.get("chunk_index", index)}
- **标题路径**: {chunk.metadata.get("title_path", "")}
- **章节标题**: {chunk.metadata.get("section_title", "")}
- **章节索引**: {chunk.metadata.get("section_index", "")}
- **章节ID**: {chunk.metadata.get("section_id", "")}
- **章节内分块索引**: {chunk.metadata.get("child_chunk_index", "")}

## 内容
{chunk.page_content}
"""
        file_path = self.chunks_dir / f"{self.markdown_prefix}_{index:04d}.md"
        file_path.write_text(content, encoding="utf-8")


