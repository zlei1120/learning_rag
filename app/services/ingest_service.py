from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.deps import AppError
from app.core.database import ensure_rag_storage_ready
from app.models.ingest_job import IngestJob
from app.repositories.blog_post_repository import BlogPostRepository
from app.repositories.ingest_job_repository import IngestJobRepository
from app.repositories.rag_chunk_repository import RagChunkRepository
from app.repositories.rag_document_repository import RagDocumentRepository
from app.repositories.rag_image_repository import RagImageRepository
from app.services.blog_source_service import BlogSourceService
from app.services.embedding_service import EmbeddingService
from app.services.image_understanding_service import ImageUnderstandingService
from app.services.markdown_ingest_service import MarkdownIngestService


class IngestService:
    """串联博客文章同步、图文抽取与任务状态写入。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.blog_post_repository = BlogPostRepository(session)
        self.rag_document_repository = RagDocumentRepository(session)
        self.rag_chunk_repository = RagChunkRepository(session)
        self.rag_image_repository = RagImageRepository(session)
        self.ingest_job_repository = IngestJobRepository(session)
        self.blog_source_service = BlogSourceService()
        self.markdown_ingest_service = MarkdownIngestService()
        self.embedding_service = EmbeddingService()
        self.image_understanding_service = ImageUnderstandingService()

    def sync_single_post(self, *, post_id: str | None, slug: str | None, force_rebuild: bool) -> IngestJob:
        """同步单篇文章到 RAG 存储。"""
        ensure_rag_storage_ready()
        job = self.ingest_job_repository.create_job(
            job_type="single_post_sync",
            target_post_id=post_id,
            target_slug=slug,
            payload_json={"post_id": post_id, "slug": slug, "force_rebuild": force_rebuild},
        )
        self.session.commit()

        try:
            self.ingest_job_repository.mark_running(job)
            self.session.commit()

            post = self._load_single_post(post_id=post_id, slug=slug)
            source_document = self.blog_source_service.build_source_document(post)
            markdown_result = self.markdown_ingest_service.parse(
                slug=source_document.slug,
                title=source_document.title,
                content=source_document.content,
            )

            document = self.rag_document_repository.upsert_from_source(source_document)
            chunks = self.rag_chunk_repository.replace_for_document(document.id, markdown_result.chunks)
            embeddings = self.embedding_service.embed_texts([chunk.content for chunk in markdown_result.chunks])
            self.rag_chunk_repository.replace_embeddings(
                chunks,
                embeddings,
                embedding_model=self.embedding_service.resolved_model_name,
            )

            image_features = self.image_understanding_service.describe_images(markdown_result.images)
            images = self.rag_image_repository.replace_for_document(document.id, markdown_result.images, image_features)
            self.rag_image_repository.rebuild_chunk_links(chunks, images)
            self.rag_document_repository.mark_succeeded(document)
            self.session.commit()

            self.ingest_job_repository.mark_succeeded(job)
            self.session.commit()
            return job
        except AppError as exc:
            self.session.rollback()
            self.ingest_job_repository.mark_failed(job, exc.message)
            self.session.commit()
            raise
        except Exception as exc:
            self.session.rollback()
            self.ingest_job_repository.mark_failed(job, str(exc))
            self.session.commit()
            raise

    def rebuild_posts(self, *, scope: str, force: bool) -> IngestJob:
        """按范围重建文章索引。当前先统一走完整同步流程。"""
        ensure_rag_storage_ready()
        job_type = {
            "all": "full_rebuild",
            "embeddings_only": "embedding_rebuild",
            "image_features_only": "image_feature_rebuild",
        }[scope]
        job = self.ingest_job_repository.create_job(
            job_type=job_type,
            payload_json={"scope": scope, "force": force},
        )
        self.session.commit()

        try:
            self.ingest_job_repository.mark_running(job)
            self.session.commit()

            posts = self.blog_post_repository.list_posts_for_sync()
            for post in posts:
                self._sync_post_record(post)

            self.session.commit()
            self.ingest_job_repository.mark_succeeded(job)
            self.session.commit()
            return job
        except Exception as exc:
            self.session.rollback()
            self.ingest_job_repository.mark_failed(job, str(exc))
            self.session.commit()
            raise

    def get_job(self, job_id: str) -> IngestJob:
        """读取任务状态。"""
        job = self.ingest_job_repository.get_by_id(job_id)
        if job is None:
            raise AppError(
                error_code="not_found",
                message="找不到对应的同步任务。",
                status_code=404,
            )
        return job

    def _load_single_post(self, *, post_id: str | None, slug: str | None):
        """读取单篇待同步文章，不存在时抛出可解释错误。"""
        post = None
        if post_id:
            post = self.blog_post_repository.get_post_by_id(post_id)
        if post is None and slug:
            post = self.blog_post_repository.get_post_by_slug(slug)

        if post is None:
            raise AppError(
                error_code="post_not_found",
                message="找不到要同步的文章，或该文章当前未发布。",
                status_code=404,
            )
        return post

    def _sync_post_record(self, post) -> None:
        """把单篇文章完整写入 RAG 存储。"""
        source_document = self.blog_source_service.build_source_document(post)
        markdown_result = self.markdown_ingest_service.parse(
            slug=source_document.slug,
            title=source_document.title,
            content=source_document.content,
        )
        document = self.rag_document_repository.upsert_from_source(source_document)
        chunks = self.rag_chunk_repository.replace_for_document(document.id, markdown_result.chunks)
        embeddings = self.embedding_service.embed_texts([chunk.content for chunk in markdown_result.chunks])
        self.rag_chunk_repository.replace_embeddings(
            chunks,
            embeddings,
            embedding_model=self.embedding_service.resolved_model_name,
        )
        image_features = self.image_understanding_service.describe_images(markdown_result.images)
        images = self.rag_image_repository.replace_for_document(document.id, markdown_result.images, image_features)
        self.rag_image_repository.rebuild_chunk_links(chunks, images)
        self.rag_document_repository.mark_succeeded(document)
