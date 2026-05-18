from pathlib import Path
from typing import List, Optional

import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from config import Config, get_config
from embedder import EmbeddingModel
from chunk_saver import ChunkSaver


class SemanticChunker:
    def __init__(
        self,
        config: Optional[Config] = None,
        breakpoint_threshold: float = 0.5,
        chunks_dir: str = "./data/chunks",
    ):
        """
        初始化语义分块器。
        Args:
            config: 配置对象
            breakpoint_threshold: 语义断点阈值（0-1，越大越容易断开）
            chunks_dir: 分块数据存储目录
        """
        self.config = config or get_config()
        self.breakpoint_threshold = breakpoint_threshold
        self.min_chunk_size = 100
        self.max_chunk_size = 512
        self.chunks_dir = Path(chunks_dir)
        # 创建存储目录。
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_saver = ChunkSaver(
            chunks_dir=self.chunks_dir,
            markdown_prefix="semantic_chunk",
            markdown_title="Semantic Chunk",
        )
        self._sentence_splitter = RecursiveCharacterTextSplitter(
            chunk_size=100,
            chunk_overlap=0,  # 根据标点裁剪，所以这里不需要 overlap。
            separators=["\n\n", "\n", "。", ".", "！", "!", "？", "?", "；", ";"],
            is_separator_regex=False,
        )
        self._embedding = self._create_embedding()  # 把句子转成向量，用于计算相似度。
        logger.info(
            "语义分块器初始化：threshold={}, min={}, max={}",
            breakpoint_threshold,
            self.min_chunk_size,
            self.max_chunk_size,
        )

    def _create_embedding(self) -> Embeddings:
        """创建嵌入模型实例。"""
        return EmbeddingModel(self.config).embeddings


    # 这里有点看不明白，但是不重要，后面再补，只需要知道这个公式可以计算向量是否相似就行。
    def _compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度。"""
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        return float(np.dot(arr1, arr2) / (np.linalg.norm(arr1) * np.linalg.norm(arr2)))

    # 根据语义相似度合并文本。
    def _split_text(self, text: str) -> List[str]:
        # 根据标点符号切句。
        sentences = self._sentence_splitter.split_text(text)
        if not sentences:
            return []
        if len(sentences) == 1:
            return sentences
        # 转成向量，方便后面计算相似度。
        vector_list = self._embedding.embed_documents(sentences)
        # 新合并出的文本列表。
        chunks = []
        # 第一段先作为当前块的起点。
        current_chunk = sentences[0]

        for i in range(1, len(sentences)):
            next_sentence = sentences[i]
            similarity = self._compute_similarity(vector_list[i - 1], vector_list[i])
            # 合并条件：
            # 1. 合并后长度不能超过 max_chunk_size；
            # 2. 语义相似，或者当前块还没达到最小长度。
            merged_length = len(current_chunk) + 1 + len(next_sentence)
            should_merge = merged_length <= self.max_chunk_size and (
                similarity > self.breakpoint_threshold
                or len(current_chunk) < self.min_chunk_size
            )
            # 如果可以合并。
            if should_merge:
                current_chunk += " " + next_sentence
                # 这里不 append，因为后面可能还能继续合并。
                continue
            # 不能合并时，说明 current_chunk 已经成型，可以加入结果。
            chunks.append(current_chunk)
            # 下一块从当前句子开始。
            current_chunk = next_sentence

        # 最后还会剩下一个块。
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def _split_document(self, documents: List[Document]) -> List[Document]:
        """把文档列表切成 Document chunk 列表。"""
        chunks = []
        logger.info("开始语义分块处理")
        for doc in documents:
            chunk_texts = self._split_text(doc.page_content)
            for chunk_index, chunk_text in enumerate(chunk_texts):
                # 复制 metadata，避免多个 chunk 共享同一个 dict。
                metadata = dict(doc.metadata)
                metadata["chunk_index"] = chunk_index
                metadata["chunk_size"] = len(chunk_text)
                chunks.append(Document(page_content=chunk_text, metadata=metadata))
        return chunks

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """对外入口：优先读缓存，否则执行语义切分并保存结果。"""
        if not documents:
            logger.warning("输入文档列表为空")
            return []

        chunks = self._split_document(documents)
        logger.info("语义切分完成：{} 个 chunk", len(chunks))
        if chunks:
            self.chunk_saver.save_chunks(chunks)
        return chunks
