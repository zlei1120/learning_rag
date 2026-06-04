from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.services.retrieval_service import RetrievedChunk

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


class RerankService:
    """封装百炼 rerank 能力，并提供本地兜底排序。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = self._create_client()

    def rerank(self, query: str, chunks: list[RetrievedChunk], *, top_k: int | None = None) -> list[RetrievedChunk]:
        """对文本召回结果做重排。"""
        if not chunks:
            return []

        limit = top_k or self.settings.chat_retrieval_top_k
        if self.client is None:
            return self._fallback_rerank(query, chunks, top_k=limit)

        try:
            response = self.client.post(
                "/reranks",
                body={
                    "model": self.settings.rerank_model,
                    "query": query,
                    "documents": [chunk.content for chunk in chunks],
                    "top_n": limit,
                    "return_documents": False,
                },
                cast_to=object,
            )
            return self._apply_model_rerank_response(chunks, response, top_k=limit)
        except Exception:
            return self._fallback_rerank(query, chunks, top_k=limit)

    def _create_client(self) -> OpenAI | None:
        """初始化百炼 rerank 客户端。"""
        if OpenAI is None or not self.settings.openai_api_key:
            return None

        return OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.rerank_base_url,
        )

    def _apply_model_rerank_response(
        self,
        chunks: list[RetrievedChunk],
        response: Any,
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """把 rerank 响应映射回原始 chunk。"""
        results = self._extract_results(response)
        reranked: list[RetrievedChunk] = []

        for item in results:
            index = self._extract_index(item)
            score = self._extract_score(item)
            if index is None or index < 0 or index >= len(chunks):
                continue

            chunk = chunks[index]
            reranked.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    slug=chunk.slug,
                    title=chunk.title,
                    title_path=chunk.title_path,
                    content=chunk.content,
                    token_estimate=chunk.token_estimate,
                    score=score if score is not None else chunk.score,
                )
            )

        if reranked:
            return reranked[:top_k]

        return self._fallback_rerank("", chunks, top_k=top_k)

    @staticmethod
    def _extract_results(response: Any) -> list[Any]:
        """兼容 dict 和 SDK 对象两种返回结构。"""
        if isinstance(response, dict):
            results = response.get("results")
            return results if isinstance(results, list) else []

        results = getattr(response, "results", None)
        return results if isinstance(results, list) else []

    @staticmethod
    def _extract_index(item: Any) -> int | None:
        """从 rerank 结果中读取原文档下标。"""
        if isinstance(item, dict):
            value = item.get("index")
        else:
            value = getattr(item, "index", None)

        return int(value) if isinstance(value, int | str) and str(value).isdigit() else None

    @staticmethod
    def _extract_score(item: Any) -> float | None:
        """从 rerank 结果中读取相关性分数。"""
        if isinstance(item, dict):
            value = item.get("relevance_score") or item.get("score")
        else:
            value = getattr(item, "relevance_score", None) or getattr(item, "score", None)

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fallback_rerank(query: str, chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
        """没有 rerank 服务时，按召回分数和关键词命中做兜底排序。"""
        query_lower = query.lower()

        def sort_key(chunk: RetrievedChunk) -> tuple[float, int]:
            keyword_bonus = 1 if query_lower and query_lower in chunk.content.lower() else 0
            return chunk.score, keyword_bonus

        return sorted(chunks, key=sort_key, reverse=True)[:top_k]
