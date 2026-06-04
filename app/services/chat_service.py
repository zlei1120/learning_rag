from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import UsageInfo
from app.services.answer_service import AnswerResult, AnswerService
from app.services.chat_response_formatter import build_related_images, build_source_items
from app.services.context_budget_service import build_default_context_budget
from app.services.rerank_service import RerankService
from app.services.retrieval_service import RetrievalResult, RetrievalService, RetrievedChunk, RetrievedImage


class ChatGraphState(TypedDict, total=False):
    """LangGraph 单轮问答图状态。"""

    question: str
    retrieval_result: RetrievalResult
    chunks: list[RetrievedChunk]
    images: list[RetrievedImage]
    answer_result: AnswerResult


class ChatService:
    """执行单轮问答主流程。"""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.retrieval_service = RetrievalService(session, self.settings)
        self.rerank_service = RerankService(self.settings)
        self.answer_service = AnswerService(self.settings)

    def answer(self, *, request: ChatRequest, session_id: str) -> ChatResponse:
        """运行问答图并组装接口响应。"""
        state = self._build_graph().invoke({"question": request.message})
        chunks = state.get("chunks", [])
        images = state.get("images", [])
        answer_result = state.get("answer_result") or AnswerResult(
            answer="根据当前已同步的文章内容，我还没有找到足够依据回答这个问题。"
        )

        return ChatResponse(
            session_id=session_id,
            answer=answer_result.answer,
            status="completed",
            sources=build_source_items(chunks, include_sources=request.include_sources),
            related_images=build_related_images(images, include_related_images=request.include_related_images),
            context_budget=build_default_context_budget(self.settings) if request.debug_context else None,
            usage=UsageInfo(
                prompt_tokens=answer_result.prompt_tokens,
                completion_tokens=answer_result.completion_tokens,
                total_tokens=answer_result.total_tokens,
            ),
        )

    def _build_graph(self):
        """构建最小问答图：召回 -> 重排 -> 生成。"""
        workflow = StateGraph(ChatGraphState)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("rerank", self._rerank_node)
        workflow.add_node("generate", self._generate_node)
        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "rerank")
        workflow.add_edge("rerank", "generate")
        workflow.add_edge("generate", END)
        return workflow.compile()

    def _retrieve_node(self, state: ChatGraphState) -> ChatGraphState:
        """召回文本块和图片文本特征。"""
        result = self.retrieval_service.retrieve(state["question"])
        return {
            **state,
            "retrieval_result": result,
            "chunks": result.chunks,
            "images": result.images,
        }

    def _rerank_node(self, state: ChatGraphState) -> ChatGraphState:
        """对文本块进行重排。"""
        chunks = self.rerank_service.rerank(
            state["question"],
            state.get("chunks", []),
            top_k=self.settings.chat_retrieval_top_k,
        )
        return {
            **state,
            "chunks": chunks,
        }

    def _generate_node(self, state: ChatGraphState) -> ChatGraphState:
        """基于最终上下文生成回答。"""
        answer_result = self.answer_service.generate_answer(
            question=state["question"],
            chunks=state.get("chunks", []),
            images=state.get("images", []),
        )
        return {
            **state,
            "answer_result": answer_result,
        }
