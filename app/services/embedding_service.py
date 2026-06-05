from __future__ import annotations

import hashlib
from itertools import islice
from typing import Iterator

from app.core.config import Settings, get_settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


class EmbeddingService:
    """封装文本向量生成，并在本地缺少凭据时提供开发级占位向量。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = self._create_client()

    @property
    def resolved_model_name(self) -> str:
        """返回当前实际使用的向量模型名。"""
        if self.client is None:
            return "mock-embedding-local-v1"
        return self.settings.embedding_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。"""
        if not texts:
            return []

        if self.client is None:
            return [self._build_mock_embedding(text) for text in texts]

        vectors: list[list[float]] = []
        # 百炼当前单次 embedding 输入上限是 10，这里再做一次运行时保护，
        # 避免环境变量被误配后同步链路直接失败。
        batch_size = min(max(self.settings.embedding_batch_size, 1), 10)
        for batch in self._batched(texts, batch_size):
            response = self.client.embeddings.create(
                model=self.settings.embedding_model,
                input=batch,
            )
            vectors.extend([list(item.embedding) for item in response.data])
        return vectors

    def _create_client(self) -> OpenAI | None:
        """按当前配置初始化 OpenAI 兼容客户端。"""
        if OpenAI is None or not self.settings.openai_api_key:
            return None
        return OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )

    @staticmethod
    def _build_mock_embedding(text: str, dim: int = 32) -> list[float]:
        """生成稳定的本地占位向量，保证开发链路可跑通。"""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < dim:
            for byte in digest:
                values.append(round((byte / 255.0) * 2 - 1, 6))
                if len(values) == dim:
                    break
            digest = hashlib.sha256(digest).digest()
        return values

    @staticmethod
    def _batched(items: list[str], size: int) -> Iterator[list[str]]:
        """把长列表切成固定大小批次。"""
        iterator = iter(items)
        while batch := list(islice(iterator, size)):
            yield batch
