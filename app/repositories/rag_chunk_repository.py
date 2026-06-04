from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.rag_chunk import RagChunk
from app.models.rag_embedding import RagEmbedding

if TYPE_CHECKING:
    from app.services.markdown_ingest_service import ChunkDraft


class RagChunkRepository:
    """管理文本块和向量记录。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_document(self, document_id: str, chunk_drafts: list[ChunkDraft]) -> list[RagChunk]:
        """整体替换某篇文档的 chunk 记录。"""
        self.session.execute(delete(RagChunk).where(RagChunk.document_id == document_id))

        chunks: list[RagChunk] = []
        for draft in chunk_drafts:
            chunk = RagChunk(
                document_id=document_id,
                section_id=draft.section_id,
                title_path=draft.title_path,
                section_title=draft.section_title,
                heading_level=draft.heading_level,
                section_index=draft.section_index,
                chunk_index=draft.chunk_index,
                child_chunk_index=draft.child_chunk_index,
                content=draft.content,
                content_hash=draft.content_hash,
                token_estimate=draft.token_estimate,
                has_images=draft.has_images,
            )
            chunks.append(chunk)

        self.session.add_all(chunks)
        self.session.flush()
        return chunks

    def replace_embeddings(
        self,
        chunks: list[RagChunk],
        vectors: list[list[float]],
        *,
        embedding_model: str,
        embedding_version: str = "v1",
    ) -> list[RagEmbedding]:
        """为当前 chunk 列表整体重建向量记录。"""
        if len(chunks) != len(vectors):
            raise ValueError("chunk 数量和向量数量不一致。")

        embeddings: list[RagEmbedding] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            embeddings.append(
                RagEmbedding(
                    chunk_id=chunk.id,
                    embedding_model=embedding_model,
                    embedding_dim=len(vector),
                    embedding_version=embedding_version,
                    embedding_vector=vector,
                )
            )

        self.session.add_all(embeddings)
        self.session.flush()
        return embeddings
