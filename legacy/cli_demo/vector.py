from typing import List, Optional
from langchain_chroma import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.documents import Document
from loguru import logger

from config import Config
from embedder import EmbeddingModel


class VectorStoreManager:
    """向量数据库管理器"""
    def __init__(self, config: Config, collection_name: str = "rag_documents"):
        self.collection_name = collection_name
        self.config = config 
        self.persist_directory = self.config.chroma_persist_dir
        self._embedding_model = EmbeddingModel(self.config)
        self._vectorstore: Optional[Chroma] = None
        logger.info(
            f"向量存储管理器初始化: persist_directory={self.persist_directory}, "
            f"collection={self.collection_name}"
        )

    @property
    def vectorstore(self) -> Chroma:
        """获取向量存储实例"""
        if self._vectorstore is None:
            self._vectorstore = self._create_vectorstore()
        return self._vectorstore

    def _create_vectorstore(self) -> Chroma:
        chroma_db = Chroma(
            collection_name=self.collection_name,
            embedding_function=self._embedding_model.embeddings,
            persist_directory=self.persist_directory,
        )
       
        logger.info(f"向量存储 {self.collection_name}，已创建新实例")
        return chroma_db

    def add_documents(self, documents: List[Document]) -> None:
        """将文档写入向量库。"""
        if not documents:
            logger.warning("没有文档可写入向量存储")
            return

        # 过滤 metadata 中包含复杂对象的文档，避免 Chroma 存储失败
        valid_docs = filter_complex_metadata(documents)
        if not valid_docs:
            logger.warning("没有有效文档可写入向量存储")
            return

        self.vectorstore.add_documents(valid_docs)
        logger.info(f"已写入 {len(valid_docs)} 条文档到向量存储 {self.collection_name}")

    def similarity_search(self, query: str, top_k: int = 5) -> List[Document]:
        if self._vectorstore is None or self.vectorstore._collection.count() == 0:
            logger.warning("向量存储为空，无法执行相似度搜索")
            return []
        results = self.vectorstore.similarity_search(query, k=self.config.top_k or top_k)
        logger.info(f"相似度搜索完成: query='{query}', results={len(results)}")
        return results

    def similarity_search_with_score(
        self, query: str, top_k: int = 5
    ) -> List[tuple[Document, float]]:
        if self._vectorstore is None or self.vectorstore._collection.count() == 0:
            logger.warning("向量存储为空，无法执行相似度搜索")
            return []
        # 优先使用传入的top_k参数，如果未指定则使用config中的值
        k = top_k if top_k else self.config.top_k
        results = self.vectorstore.similarity_search_with_score(
            query, k=k
        )
        logger.info(f"相似度搜索完成: query='{query}', results={len(results)}")
        return results

    # 返回给 LangChain 使用的 retriever 接口
    def as_retriever(self, **kwargs):
        search_kwargs = kwargs.pop("search_kwargs", {})
        if "k" not in search_kwargs:
            search_kwargs["k"] = self.config.top_k

        return self.vectorstore.as_retriever(search_kwargs=search_kwargs, **kwargs)
