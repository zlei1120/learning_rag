from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.chat import ChatRequest
from app.services.answer_service import AnswerResult
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalResult, RetrievedChunk, RetrievedImage
from app.services.session_service import ConversationMessage, SessionContext


class FakeSession:
    """多轮问答测试使用的空会话替身。"""

    def commit(self) -> None:
        return None


class FakeRetrievalService:
    """记录检索查询，返回固定正文与图片。"""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def retrieve(self, query: str) -> RetrievalResult:
        self.queries.append(query)
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
                    content="先确认 PostgreSQL 服务和 5432 端口配置。",
                    token_estimate=12,
                    score=0.9,
                )
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
                    caption="截图展示端口和账号权限。",
                    feature_summary="图片里有 5432 端口和账号权限检查。",
                    token_estimate=10,
                    score=0.8,
                )
            ],
        )

    def expand_parent_chunks(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return chunks


class FakeRerankService:
    """保持当前排序。"""

    def rerank(self, query: str, chunks: list[RetrievedChunk], *, top_k: int | None = None) -> list[RetrievedChunk]:
        return chunks[: top_k or len(chunks)]


class StatefulSessionService:
    """用内存模拟真实会话持久化，验证多轮上下文传递。"""

    def __init__(self) -> None:
        self.messages_by_session: dict[str, list[ConversationMessage]] = {}
        self.summary_by_session: dict[str, str | None] = {}
        self.checkpoint_by_session: dict[str, str | None] = {}

    def get_or_create_context(self, *, session_id: str, user_key: str | None = None) -> SessionContext:
        return SessionContext(
            session_row_id=f"row-{session_id}",
            session_id=session_id,
            user_key=user_key,
            status="active",
            summary_text=self.summary_by_session.get(session_id),
            recent_messages=self.messages_by_session.get(session_id, [])[-4:],
            created_at=None,
            updated_at=None,
            last_message_at=None,
            last_checkpoint_ref=self.checkpoint_by_session.get(session_id),
        )

    def build_retrieval_query(self, *, question: str, session_context: SessionContext) -> str:
        if session_context.recent_messages:
            return f"最近问题：{session_context.recent_messages[-1].content}\n当前问题：{question}"
        return question

    def record_exchange(
        self,
        *,
        session_id: str,
        user_key: str | None,
        user_message: str,
        assistant_message: str,
        source_payload: dict[str, object] | None = None,
        checkpoint_ref: str | None = None,
    ) -> SessionContext:
        messages = self.messages_by_session.setdefault(session_id, [])
        next_index = len(messages) + 1
        messages.append(
            ConversationMessage(
                message_id=f"{session_id}-user-{next_index}",
                role="user",
                content=user_message,
                message_index=next_index,
                token_estimate=10,
            )
        )
        assistant_index = next_index + 1
        messages.append(
            ConversationMessage(
                message_id=f"{session_id}-assistant-{assistant_index}",
                role="assistant",
                content=assistant_message,
                message_index=assistant_index,
                token_estimate=12,
            )
        )
        self.checkpoint_by_session[session_id] = checkpoint_ref
        return self.get_or_create_context(session_id=session_id, user_key=user_key)

    def get_session_response(self, *, session_id: str):
        return self.get_or_create_context(session_id=session_id)


class StatefulMemoryService:
    """模拟摘要记忆更新。"""

    def __init__(self, session_service: StatefulSessionService) -> None:
        self.session_service = session_service

    def refresh_session_summary(self, session_context: SessionContext) -> str | None:
        if len(session_context.recent_messages) >= 4:
            summary = "本会话围绕数据库配置和 5432 端口继续追问。"
            self.session_service.summary_by_session[session_context.session_id] = summary
            return summary
        return None


class MultiTurnAnswerService:
    """根据多轮上下文返回不同回答，并验证历史传入。"""

    def __init__(self) -> None:
        self.calls = 0

    def generate_answer(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        images: list[RetrievedImage],
        summary_text=None,
        recent_messages=None,
    ) -> AnswerResult:
        self.calls += 1
        if self.calls == 1:
            assert recent_messages == []
            assert summary_text in (None, "")
            return AnswerResult(answer="第一步先确认 PostgreSQL 服务已经启动，再检查 5432 端口。")

        if self.calls == 2:
            assert recent_messages is not None
            assert len(recent_messages) == 2
            assert recent_messages[0].content == "数据库教程的第一步是什么？"
            assert "PostgreSQL" in recent_messages[1].content
            return AnswerResult(answer="这里的端口指 PostgreSQL 对外监听的 5432 端口。")

        assert recent_messages is not None
        assert summary_text in (None, "")
        assert recent_messages == []
        return AnswerResult(answer="新的会话不应继承旧上下文。")


def test_chat_multi_turn_keeps_session_history_and_isolates_new_session():
    """同一会话应带上历史追问，新会话不应继承旧会话上下文。"""
    service = ChatService(
        session=FakeSession(),
        settings=Settings(openai_api_key=""),
    )
    session_service = StatefulSessionService()
    service.retrieval_service = FakeRetrievalService()
    service.rerank_service = FakeRerankService()
    service.answer_service = MultiTurnAnswerService()
    service.session_service = session_service
    service.memory_service = StatefulMemoryService(session_service)

    first_response = service.answer(
        request=ChatRequest(message="数据库教程的第一步是什么？"),
        session_id="sess_multi_turn_001",
    )
    second_response = service.answer(
        request=ChatRequest(message="这里的端口是什么意思？"),
        session_id="sess_multi_turn_001",
    )
    third_response = service.answer(
        request=ChatRequest(message="这里的端口是什么意思？"),
        session_id="sess_multi_turn_002",
    )

    assert "PostgreSQL" in first_response.answer
    assert "5432" in second_response.answer
    assert "不应继承旧上下文" in third_response.answer
    assert service.retrieval_service.queries[0] == "数据库教程的第一步是什么？"
    assert "最近问题" in service.retrieval_service.queries[1]
    assert service.retrieval_service.queries[2] == "这里的端口是什么意思？"
