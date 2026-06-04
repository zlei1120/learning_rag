from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.rag_chunk import RagChunk
from app.models.rag_image import RagChunkImage, RagImage, RagImageFeature

if TYPE_CHECKING:
    from app.services.image_understanding_service import ImageFeatureDraft
    from app.services.markdown_ingest_service import ImageDraft


class RagImageRepository:
    """管理图片、图片特征和图文关联。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_document(
        self,
        document_id: str,
        image_drafts: list[ImageDraft],
        image_features: list[ImageFeatureDraft],
    ) -> list[RagImage]:
        """整体替换某篇文档的图片及其文本特征。"""
        if len(image_drafts) != len(image_features):
            raise ValueError("图片数量和图片特征数量不一致。")

        self.session.execute(delete(RagImage).where(RagImage.document_id == document_id))

        images: list[RagImage] = []
        for draft, feature in zip(image_drafts, image_features, strict=True):
            image = RagImage(
                document_id=document_id,
                source_url=draft.source_url,
                normalized_url=draft.normalized_url,
                alt_text=draft.alt_text,
                markdown_ref=draft.markdown_ref,
                title_path=draft.title_path,
                section_id=draft.section_id,
                image_index=draft.image_index,
                neighbor_text_before=draft.neighbor_text_before,
                neighbor_text_after=draft.neighbor_text_after,
                image_hash=draft.image_hash,
            )
            image.features.append(
                RagImageFeature(
                    ocr_text=feature.ocr_text,
                    ocr_text_summary=feature.ocr_text_summary,
                    caption_text=feature.caption_text,
                    feature_summary=feature.feature_summary,
                    ocr_model=feature.ocr_model,
                    caption_model=feature.caption_model,
                    feature_hash=feature.feature_hash,
                    status=feature.status,
                    error_message=feature.error_message,
                    token_estimate=feature.token_estimate,
                )
            )
            images.append(image)

        self.session.add_all(images)
        self.session.flush()
        return images

    def rebuild_chunk_links(self, chunks: list[RagChunk], images: list[RagImage]) -> list[RagChunkImage]:
        """按 section 建立最小图文关联。"""
        chunk_links: list[RagChunkImage] = []
        chunk_by_section: dict[str, list[RagChunk]] = {}

        for chunk in chunks:
            if chunk.section_id is None:
                continue
            chunk_by_section.setdefault(chunk.section_id, []).append(chunk)

        for image in images:
            if image.section_id is None:
                continue

            candidates = chunk_by_section.get(image.section_id, [])
            if not candidates:
                continue

            best_chunk = candidates[0]
            relation_type = "same_section"
            distance_score = 0.6

            for candidate in candidates:
                if image.markdown_ref and image.markdown_ref in candidate.content:
                    best_chunk = candidate
                    relation_type = "explicit_markdown_reference"
                    distance_score = 1.0
                    break

            chunk_links.append(
                RagChunkImage(
                    chunk_id=best_chunk.id,
                    image_id=image.id,
                    relation_type=relation_type,
                    distance_score=distance_score,
                )
            )

        self.session.add_all(chunk_links)
        self.session.flush()
        return chunk_links
