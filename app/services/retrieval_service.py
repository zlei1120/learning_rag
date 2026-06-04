from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.rag_chunk import RagChunk
from app.models.rag_document import RagDocument
from app.models.rag_embedding import RagEmbedding
from app.models.rag_image import RagImage, RagImageFeature
from app.services.embedding_service import EmbeddingService


@dataclass(slots=True)
class RetrievedChunk:
    """问答链路召回到的正文片段。"""

    chunk_id: str
    document_id: str
    slug: str
    title: str
    title_path: str | None
    content: str
    token_estimate: int | None
    score: float


@dataclass(slots=True)
class RetrievedImage:
    """问答链路召回到的图片文本特征。"""

    image_id: str
    document_id: str
    slug: str
    title: str
    url: str
    alt_text: str | None
    title_path: str | None
    caption: str | None
    feature_summary: str | None
    score: float


@dataclass(slots=True)
class RetrievalResult:
    """文本和图片召回结果。"""

    chunks: list[RetrievedChunk]
    images: list[RetrievedImage]


class RetrievalService:
    """从 RAG 表中召回文本 chunk 和图片文本特征。"""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(self.settings)

    def retrieve(self, query: str) -> RetrievalResult:
        """执行首版图文召回。"""
        chunks = self.retrieve_text_chunks(query, top_k=self.settings.chat_retrieval_top_k)
        images = self.retrieve_image_features(query, top_k=self.settings.chat_image_top_k)
        return RetrievalResult(chunks=chunks, images=images)

    def retrieve_text_chunks(self, query: str, *, top_k: int) -> list[RetrievedChunk]:
        """优先用向量召回文本块，失败时回退到关键词召回。"""
        try:
            query_vector = self.embedding_service.embed_texts([query])[0]
            statement = (
                select(
                    RagChunk,
                    RagDocument,
                    RagEmbedding.embedding_vector.cosine_distance(query_vector).label("distance"),
                )
                .join(RagDocument, RagChunk.document_id == RagDocument.id)
                .join(RagEmbedding, RagEmbedding.chunk_id == RagChunk.id)
                .where(RagDocument.published.is_(True))
                .order_by("distance")
                .limit(top_k)
            )
            rows = self.session.execute(statement).all()
            chunks = [
                self._build_retrieved_chunk(chunk, document, score=1.0 / (1.0 + float(distance or 0.0)))
                for chunk, document, distance in rows
            ]
            if chunks:
                return chunks
        except Exception:
            # 数据库未启用 pgvector、维度不匹配或本地测试替身不支持时，走关键词兜底。
            pass

        return self._retrieve_text_chunks_by_keyword(query, top_k=top_k)

    def retrieve_image_features(self, query: str, *, top_k: int) -> list[RetrievedImage]:
        """召回图片 OCR / caption 生成的文本特征。"""
        conditions = self._build_keyword_conditions(
            query,
            RagImageFeature.feature_summary,
            RagImageFeature.ocr_text_summary,
            RagImageFeature.caption_text,
            RagImage.alt_text,
        )
        statement = (
            select(RagImage, RagImageFeature, RagDocument)
            .join(RagImageFeature, RagImageFeature.image_id == RagImage.id)
            .join(RagDocument, RagImage.document_id == RagDocument.id)
            .where(RagDocument.published.is_(True))
            .where(RagImageFeature.status.in_(["succeeded", "fallback"]))
            .order_by(RagImage.image_index.asc())
            .limit(top_k)
        )
        if conditions:
            statement = statement.where(or_(*conditions))

        rows = self.session.execute(statement).all()
        return [
            self._build_retrieved_image(image, feature, document, score=self._keyword_score(query, feature.feature_summary or ""))
            for image, feature, document in rows
        ]

    def _retrieve_text_chunks_by_keyword(self, query: str, *, top_k: int) -> list[RetrievedChunk]:
        """在向量召回不可用时用关键词召回文本块。"""
        conditions = self._build_keyword_conditions(query, RagChunk.content, RagChunk.title_path, RagDocument.title)
        statement = (
            select(RagChunk, RagDocument)
            .join(RagDocument, RagChunk.document_id == RagDocument.id)
            .where(RagDocument.published.is_(True))
            .order_by(RagDocument.source_updated_at.desc().nullslast(), RagChunk.chunk_index.asc())
            .limit(top_k)
        )
        if conditions:
            statement = statement.where(or_(*conditions))

        rows = self.session.execute(statement).all()
        return [
            self._build_retrieved_chunk(chunk, document, score=self._keyword_score(query, chunk.content))
            for chunk, document in rows
        ]

    @staticmethod
    def _build_retrieved_chunk(chunk: RagChunk, document: RagDocument, *, score: float) -> RetrievedChunk:
        """把 ORM 对象转换为问答链路内部结构。"""
        return RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            slug=document.slug,
            title=document.title,
            title_path=chunk.title_path,
            content=chunk.content,
            token_estimate=chunk.token_estimate,
            score=score,
        )

    @staticmethod
    def _build_retrieved_image(
        image: RagImage,
        feature: RagImageFeature,
        document: RagDocument,
        *,
        score: float,
    ) -> RetrievedImage:
        """把图片和图片特征转换为问答链路内部结构。"""
        return RetrievedImage(
            image_id=image.id,
            document_id=document.id,
            slug=document.slug,
            title=document.title,
            url=image.source_url,
            alt_text=image.alt_text,
            title_path=image.title_path,
            caption=feature.caption_text,
            feature_summary=feature.feature_summary,
            score=score,
        )

    def _build_keyword_conditions(self, query: str, *columns) -> list[object]:
        """根据查询词构造简洁的关键词过滤条件。"""
        tokens = self._extract_query_tokens(query)
        if not tokens:
            return []

        conditions: list[object] = []
        for token in tokens[:8]:
            pattern = f"%{token}%"
            conditions.extend(column.ilike(pattern) for column in columns)
        return conditions

    @staticmethod
    def _extract_query_tokens(query: str) -> list[str]:
        """提取适合数据库模糊匹配的关键词。"""
        tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_-]{2,}", query)
        seen: set[str] = set()
        normalized_tokens: list[str] = []
        for token in tokens:
            normalized = token.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                normalized_tokens.append(normalized)
        return normalized_tokens

    @classmethod
    def _keyword_score(cls, query: str, content: str) -> float:
        """用关键词重合度给兜底召回结果一个可排序分数。"""
        tokens = cls._extract_query_tokens(query)
        if not tokens:
            return 0.1

        normalized_content = content.lower()
        hits = sum(1 for token in tokens if token in normalized_content)
        return hits / max(len(tokens), 1)
