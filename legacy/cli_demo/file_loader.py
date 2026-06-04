from pathlib import Path  # 导入 Path 类用于处理文件路径
from typing import List, Union

from loguru import logger

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)


class FileLoader:
    """文件加载器"""

    loaders = {
        ".txt": TextLoader,
        ".md": TextLoader,
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
    }

    def __init__(self) -> None:
        """初始化 FileLoader 实例，加载指定路径的文件或目录。"""

    def load_file(self, file_path: Union[str, Path]) -> List[Document]:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在：{file_path}")
        ext = file_path.suffix.lower()
        if ext not in self.loaders:
            suported_exts = ", ".join(self.loaders.keys())
            raise ValueError(f"不支持的文件类型：{ext}，仅支持 {suported_exts}")
        if ext in [".txt", ".md"]:
            # Markdown 必须按 UTF-8 原文读取，保留 `# / ## / ###` 标题符号。
            # 如果用 UnstructuredMarkdownLoader，标题结构可能会被弱化，后续就没法按标题路径切分。
            loader = TextLoader(str(file_path), encoding="utf-8")
        else:
            loader = self.loaders[ext](str(file_path))
        documents = loader.load()
        # 为每个文档片段添加来源信息
        for doc in documents:
            doc.metadata["source_file"] = str(file_path)
            doc.metadata["file_name"] = file_path.name
            doc.metadata["file_type"] = ext
        logger.info(
            "文件加载完成：{} -> {} 个文档片段",
            file_path.name,
            len(documents),
        )
        return documents

    def load_directory(
        self,
        dir_path: Union[str, Path],
    ) -> List[Document]:
        dir_path = Path(dir_path)
        all_documents: List[Document] = []
        pattern = "*"
        for suffix in self.loaders:
            # dir_path.glob 返回一个生成器，遍历匹配的文件路径
            for file_path in dir_path.glob(f"{pattern}{suffix}"):
                logger.info("正在加载文件：{}", file_path.name)
                try:
                    all_documents.extend(self.load_file(file_path))
                except Exception as exc:
                    logger.warning("跳过文件 {}：{}", file_path.name, exc)
        logger.info(
            "目录加载完成：共 {} 个文档片段",
            len(all_documents),
        )
        return all_documents

    def load(self, path: Union[str, Path]) -> List[Document]:
        """加载文件或目录。"""
        path = Path(path)
        if path.is_file():
            return self.load_file(path)
        if path.is_dir():
            return self.load_directory(path)
