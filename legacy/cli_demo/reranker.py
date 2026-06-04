"""
重排序模块

使用 Cross-Encoder 模型对检索结果进行精细化重排序。
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.documents import Document
from loguru import logger

from config import Config, get_config


class Reranker:
    """对粗检索结果进行重排序。"""
    SUPPORTED_MODELS: dict[str, str] = {
        "bge-reranker-base": "BAAI/bge-reranker-base",
        "bge-reranker-large": "BAAI/bge-reranker-large",
        "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
    }

    def __init__(
        self,
        model_name: str = "bge-reranker-base",
        config: Optional[Config] = None,
        use_gpu: bool = False,
    ) -> None:
        self.config = config or get_config()
        self.model_name = model_name
        self.use_gpu = use_gpu

        self._model: Any = None
        self._is_loaded = False

        logger.info("重排序器初始化: 模型={}", model_name)

    def _load_model(self) -> None:
        """懒加载重排序模型。"""
        if self._is_loaded:
            return

        try:
            from sentence_transformers import CrossEncoder

            full_model_name = self.SUPPORTED_MODELS.get(self.model_name, self.model_name)
            device = "cuda" if self.use_gpu else "cpu"
            self._model = CrossEncoder(full_model_name, device=device)
            self._is_loaded = True

            logger.info("重排序模型加载完成: {}", full_model_name)
        except Exception as e:
            logger.error("模型加载失败: {}", e)
            raise

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: Optional[int] = None,
    ) -> list[tuple[Document, float]]:
        """
        对文档进行重排序。
        """
        if not documents:
            return []

        limit = top_k if top_k is not None else self.config.top_k
        self._load_model()

        pairs: list[tuple[str, str]] = [(query, doc.page_content) for doc in documents]

        try:
            raw_scores = self._model.predict(pairs)
            scores = [float(score) for score in raw_scores]

            doc_scores: list[tuple[Document, float]] = list(zip(documents, scores))
            doc_scores.sort(key=lambda item: item[1], reverse=True)
            result = doc_scores[:limit]

            if result:
                logger.info(
                    "重排序完成: {} -> {} 个文档, 最高分={:.4f}",
                    len(documents),
                    len(result),
                    result[0][1],
                )
            else:
                logger.info("重排序完成: 0 个有效结果")

            return result
        except Exception as e:
            logger.error("重排序失败: {}", e)
            return [(doc, 0.0) for doc in documents[:limit]]
