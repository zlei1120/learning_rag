from __future__ import annotations

from app.core.config import Settings
from app.schemas.chat import ChatRequest
from app.services.answer_service import AnswerResult
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalResult, RetrievedChunk, RetrievedImage


class FakeSession:
    """单轮问答集成测试使用的空会话替身。"""


class FakeRetrievalService:
    """返回固定图文召回结果。"""

    def retrieve(self, query: str) -> RetrievalResult:
        assert "数据库" in query
        return RetrievalResult(
            chunks=[
                RetrievedChunk(
                    chunk_id="chunk-001",
                    document_id="doc-001",
                    slug="db-guide",
                    title="数据库教程",
                    section_id="section-001",
                    title_path="数据库教程 > 准备数据库",
                    chunk_index=0,
                    content="标题路径：数据库教程 > 准备数据库\n内容：\n先打开数据库管理页面，确认 PostgreSQL 服务已经启动，然后检查端口和账号权限。",
                    token_estimate=18,
                    score=0.9,
                ),
                RetrievedChunk(
                    chunk_id="chunk-002",
                    document_id="doc-001",
                    slug="db-guide",
                    title="数据库教程",
                    section_id="section-001",
                    title_path="数据库教程 > 第二步",
                    chunk_index=1,
                    content="标题路径：数据库教程 > 第二步\n内容：\n再执行迁移脚本，确认 RAG 表结构已经创建完成。",
                    token_estimate=14,
                    score=0.7,
                ),
            ],
            images=[
                RetrievedImage(
                    image_id="image-001",
                    document_id="doc-001",
                    slug="db-guide",
                    title="数据库教程",
                    url="/uploads/tutorial/db-step.png",
                    alt_text="数据库配置截图",
                    title_path="数据库教程 > 准备数据库",
                    caption="数据库配置截图展示端口和账号权限检查。",
                    feature_summary="图片文字摘要：5432；账号权限检查",
                    token_estimate=10,
                    score=0.8,
                )
            ],
        )

    def expand_parent_chunks(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return chunks


class FakeRerankService:
    """保持召回顺序，便于测试聚焦问答主流程。"""

    def rerank(self, query: str, chunks: list[RetrievedChunk], *, top_k: int | None = None) -> list[RetrievedChunk]:
        assert "数据库" in query
        return chunks[: top_k or len(chunks)]


class FakeAnswerService:
    """返回固定回答，便于验证响应组装。"""

    def generate_answer(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        images: list[RetrievedImage],
    ) -> AnswerResult:
        assert question == "数据库教程的主要步骤是什么？"
        assert len(chunks) == 2
        assert len(images) == 1
        return AnswerResult(
            answer="主要步骤是先确认 PostgreSQL 服务和端口配置，再检查账号权限，最后执行迁移脚本创建 RAG 表结构。",
            prompt_tokens=120,
            completion_tokens=48,
            total_tokens=168,
        )


def test_chat_single_turn_returns_answer_sources_and_images():
    """单轮问答应返回回答、来源、图片和预算调试信息。"""
    service = ChatService(
        session=FakeSession(),
        settings=Settings(
            openai_api_key="",
            chat_context_retrieval_tokens=60,
            chat_context_image_tokens=20,
        ),
    )
    service.retrieval_service = FakeRetrievalService()
    service.rerank_service = FakeRerankService()
    service.answer_service = FakeAnswerService()

    response = service.answer(
        request=ChatRequest(
            message="数据库教程的主要步骤是什么？",
            debug_context=True,
        ),
        session_id="sess_test_chat_001",
    )

    assert response.session_id == "sess_test_chat_001"
    assert response.status == "completed"
    assert "PostgreSQL" in response.answer
    assert len(response.sources) == 2
    assert response.sources[0].slug == "db-guide"
    assert len(response.related_images) == 1
    assert response.related_images[0].url == "/uploads/tutorial/db-step.png"
    assert response.context_budget is not None
    assert response.context_budget.retrieved_chunks_tokens == 60
    assert response.usage is not None
    assert response.usage.total_tokens == 168
