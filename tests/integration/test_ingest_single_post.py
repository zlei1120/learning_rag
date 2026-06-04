from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.repositories.blog_post_repository import BlogSourcePost
from app.services import ingest_service as ingest_module
from app.services.image_understanding_service import ImageFeatureDraft


@dataclass
class FakeSession:
    """记录同步流程中的关键调用，避免测试依赖真实数据库。"""

    events: list[str] = field(default_factory=list)
    commit_count: int = 0
    rollback_count: int = 0
    chunk_drafts: list[Any] = field(default_factory=list)
    image_drafts: list[Any] = field(default_factory=list)
    image_features: list[ImageFeatureDraft] = field(default_factory=list)

    def commit(self) -> None:
        self.commit_count += 1
        self.events.append("commit")

    def rollback(self) -> None:
        self.rollback_count += 1
        self.events.append("rollback")


@dataclass
class FakeJob:
    """同步任务替身。"""

    id: str
    job_type: str
    status: str
    target_post_id: str | None = None
    target_slug: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


@dataclass
class FakeDocument:
    """RAG 文档替身。"""

    id: str
    slug: str
    sync_status: str = "running"


@dataclass
class FakeChunk:
    """文本块替身。"""

    id: str
    content: str
    section_id: str | None


@dataclass
class FakeImage:
    """图片替身。"""

    id: str
    section_id: str | None
    markdown_ref: str | None


def build_blog_post() -> BlogSourcePost:
    """构造一篇包含图片的已发布博客文章。"""
    now = datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)
    return BlogSourcePost(
        id="post-001",
        title="数据库教程",
        slug="db-guide",
        content="""
## 准备数据库
先打开数据库管理页面，确认 PostgreSQL 服务已经启动。

![数据库配置截图](/uploads/tutorial/db-step.png)

然后检查端口是 5432，并确认账号具备读取文章表的权限。
""".strip(),
        excerpt="数据库配置说明",
        category="教程",
        tags=["PostgreSQL", "RAG"],
        published=True,
        date=now,
        series="FastAPI RAG",
        series_order=1,
        created_at=now,
        updated_at=now,
    )


class FakeBlogPostRepository:
    """博客真源仓储替身。"""

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def get_post_by_id(self, post_id: str) -> BlogSourcePost | None:
        self.session.events.append(f"get_post_by_id:{post_id}")
        return None

    def get_post_by_slug(self, slug: str) -> BlogSourcePost | None:
        self.session.events.append(f"get_post_by_slug:{slug}")
        return build_blog_post() if slug == "db-guide" else None


class FakeRagDocumentRepository:
    """RAG 文档仓储替身。"""

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def upsert_from_source(self, source_document) -> FakeDocument:
        self.session.events.append(f"upsert_document:{source_document.slug}")
        assert source_document.source_post_id == "post-001"
        assert source_document.published is True
        return FakeDocument(id="doc-001", slug=source_document.slug)

    def mark_succeeded(self, document: FakeDocument) -> FakeDocument:
        self.session.events.append(f"document_succeeded:{document.id}")
        document.sync_status = "succeeded"
        return document


class FakeRagChunkRepository:
    """文本块仓储替身。"""

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def replace_for_document(self, document_id: str, chunk_drafts: list[Any]) -> list[FakeChunk]:
        self.session.events.append(f"replace_chunks:{document_id}:{len(chunk_drafts)}")
        self.session.chunk_drafts = chunk_drafts
        assert document_id == "doc-001"
        assert len(chunk_drafts) >= 1
        return [
            FakeChunk(
                id=f"chunk-{index}",
                content=draft.content,
                section_id=draft.section_id,
            )
            for index, draft in enumerate(chunk_drafts)
        ]

    def replace_embeddings(self, chunks: list[FakeChunk], vectors: list[list[float]], *, embedding_model: str) -> None:
        self.session.events.append(f"replace_embeddings:{embedding_model}:{len(vectors)}")
        assert len(chunks) == len(vectors)


class FakeRagImageRepository:
    """图片仓储替身。"""

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def replace_for_document(
        self,
        document_id: str,
        image_drafts: list[Any],
        image_features: list[ImageFeatureDraft],
    ) -> list[FakeImage]:
        self.session.events.append(f"replace_images:{document_id}:{len(image_drafts)}")
        self.session.image_drafts = image_drafts
        self.session.image_features = image_features
        assert document_id == "doc-001"
        assert len(image_drafts) == 1
        assert len(image_features) == 1
        return [
            FakeImage(
                id="image-001",
                section_id=image_drafts[0].section_id,
                markdown_ref=image_drafts[0].markdown_ref,
            )
        ]

    def rebuild_chunk_links(self, chunks: list[FakeChunk], images: list[FakeImage]) -> None:
        self.session.events.append(f"rebuild_chunk_links:{len(chunks)}:{len(images)}")
        assert chunks
        assert images


class FakeIngestJobRepository:
    """同步任务仓储替身。"""

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def create_job(
        self,
        *,
        job_type: str,
        target_post_id: str | None = None,
        target_slug: str | None = None,
        trigger_source: str = "api",
        payload_json: dict[str, object] | None = None,
    ) -> FakeJob:
        self.session.events.append(f"create_job:{job_type}:{target_slug}:{trigger_source}")
        assert payload_json == {"post_id": None, "slug": "db-guide", "force_rebuild": False}
        return FakeJob(
            id="job-001",
            job_type=job_type,
            status="queued",
            target_post_id=target_post_id,
            target_slug=target_slug,
        )

    def mark_running(self, job: FakeJob) -> FakeJob:
        self.session.events.append(f"job_running:{job.id}")
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        return job

    def mark_succeeded(self, job: FakeJob) -> FakeJob:
        self.session.events.append(f"job_succeeded:{job.id}")
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        return job

    def mark_failed(self, job: FakeJob, error_message: str) -> FakeJob:
        self.session.events.append(f"job_failed:{job.id}:{error_message}")
        job.status = "failed"
        job.error_message = error_message
        return job


class FakeEmbeddingService:
    """文本向量服务替身。"""

    @property
    def resolved_model_name(self) -> str:
        return "fake-embedding-model"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert texts
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeImageUnderstandingService:
    """图片理解服务替身。"""

    def describe_images(self, image_drafts: list[Any]) -> list[ImageFeatureDraft]:
        assert len(image_drafts) == 1
        assert image_drafts[0].source_url == "/uploads/tutorial/db-step.png"
        return [
            ImageFeatureDraft(
                ocr_text="5432",
                ocr_text_summary="端口 5432",
                caption_text="数据库配置截图展示端口和账号权限检查。",
                feature_summary="数据库配置截图展示端口和账号权限检查；图中文字摘要：端口 5432",
                ocr_model="fake-ocr",
                caption_model="fake-caption",
                feature_hash="feature-hash-001",
                status="succeeded",
                error_message=None,
                token_estimate=12,
            )
        ]


def test_ingest_single_post_runs_full_indexing_pipeline(monkeypatch):
    """单篇同步应串起文章读取、分块、向量、图片特征和任务状态。"""
    session = FakeSession()
    monkeypatch.setattr(ingest_module, "ensure_rag_storage_ready", lambda: session.events.append("storage_ready"))
    monkeypatch.setattr(ingest_module, "BlogPostRepository", FakeBlogPostRepository)
    monkeypatch.setattr(ingest_module, "RagDocumentRepository", FakeRagDocumentRepository)
    monkeypatch.setattr(ingest_module, "RagChunkRepository", FakeRagChunkRepository)
    monkeypatch.setattr(ingest_module, "RagImageRepository", FakeRagImageRepository)
    monkeypatch.setattr(ingest_module, "IngestJobRepository", FakeIngestJobRepository)
    monkeypatch.setattr(ingest_module, "EmbeddingService", FakeEmbeddingService)
    monkeypatch.setattr(ingest_module, "ImageUnderstandingService", FakeImageUnderstandingService)

    service = ingest_module.IngestService(session)
    job = service.sync_single_post(post_id=None, slug="db-guide", force_rebuild=False)

    assert job.status == "succeeded"
    assert session.rollback_count == 0
    assert session.commit_count >= 4
    assert any("准备数据库" in chunk.title_path for chunk in session.chunk_drafts)
    assert session.image_drafts[0].alt_text == "数据库配置截图"
    assert session.image_features[0].status == "succeeded"
    assert session.events == [
        "storage_ready",
        "create_job:single_post_sync:db-guide:api",
        "commit",
        "job_running:job-001",
        "commit",
        "get_post_by_slug:db-guide",
        "upsert_document:db-guide",
        "replace_chunks:doc-001:1",
        "replace_embeddings:fake-embedding-model:1",
        "replace_images:doc-001:1",
        "rebuild_chunk_links:1:1",
        "document_succeeded:doc-001",
        "commit",
        "job_succeeded:job-001",
        "commit",
    ]
