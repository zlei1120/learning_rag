from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import UsageInfo
from app.services.answer_service import AnswerResult, AnswerService
from app.services.chat_response_formatter import build_related_images, build_source_items
from app.services.context_budget_service import build_default_context_budget, trim_context_by_budget
from app.services.memory_service import MemoryService
from app.services.orchestration_service import get_graph_checkpointer
from app.services.rerank_service import RerankService
from app.services.retrieval_service import RetrievalResult, RetrievalService, RetrievedChunk, RetrievedImage
from app.services.session_service import SessionContext, SessionService


class ChatGraphState(TypedDict, total=False):
    """LangGraph 问答图状态。"""

    question: str
    retrieval_query: str
    session_context: SessionContext
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
        self.session_service = SessionService(session, self.settings)
        self.memory_service = MemoryService(session, self.settings)
        self.graph = self._build_graph()

    def answer(self, *, request: ChatRequest, session_id: str) -> ChatResponse:
        """运行问答图、写入会话记录并组装接口响应。"""
        session_context = self.session_service.get_or_create_context(
            session_id=session_id,
            user_key=request.user_key,
        )
        retrieval_query = self.session_service.build_retrieval_query(
            question=request.message,
            session_context=session_context,
        )
        state = self.graph.invoke(
            {
                "question": request.message,
                "retrieval_query": retrieval_query,
                "session_context": session_context,
            },
            config={
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": "chat",
                }
            },
        )
        chunks = state.get("chunks", [])
        images = state.get("images", [])
        answer_result = state.get("answer_result") or AnswerResult(
            answer="根据当前已同步的文章内容，我还没有找到足够依据回答这个问题。"
        )
        source_items = build_source_items(chunks, include_sources=request.include_sources)
        related_images = build_related_images(images, include_related_images=request.include_related_images)

        checkpoint_ref = self._resolve_checkpoint_ref(session_id)
        persisted_context = self.session_service.record_exchange(
            session_id=session_id,
            user_key=request.user_key,
            user_message=request.message,
            assistant_message=answer_result.answer,
            source_payload={
                "sources": [item.model_dump(exclude_none=True) for item in source_items],
                "related_images": [item.model_dump(exclude_none=True) for item in related_images],
            },
            checkpoint_ref=checkpoint_ref,
        )
        self.memory_service.refresh_session_summary(persisted_context)
        self.session.commit()

        return ChatResponse(
            session_id=session_id,
            answer=answer_result.answer,
            status="completed",
            sources=source_items,
            related_images=related_images,
            context_budget=build_default_context_budget(self.settings) if request.debug_context else None,
            usage=UsageInfo(
                prompt_tokens=answer_result.prompt_tokens,
                completion_tokens=answer_result.completion_tokens,
                total_tokens=answer_result.total_tokens,
            ),
        )

    def _build_graph(self):
        """构建最小问答图：召回 -> 重排 -> 父子扩展 -> 裁剪 -> 生成。"""
        workflow = StateGraph(ChatGraphState)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("rerank", self._rerank_node)
        workflow.add_node("expand_context", self._expand_context_node)
        workflow.add_node("trim_context", self._trim_context_node)
        workflow.add_node("generate", self._generate_node)
        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "rerank")
        workflow.add_edge("rerank", "expand_context")
        workflow.add_edge("expand_context", "trim_context")
        workflow.add_edge("trim_context", "generate")
        workflow.add_edge("generate", END)
        return workflow.compile(checkpointer=get_graph_checkpointer())

    def _retrieve_node(self, state: ChatGraphState) -> ChatGraphState:
        """召回文本块和图片文本特征。"""
        result = self.retrieval_service.retrieve(state.get("retrieval_query") or state["question"])
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

    def _expand_context_node(self, state: ChatGraphState) -> ChatGraphState:
        """围绕命中 chunk 补充前后窗口，给教程类内容更多上下文。"""
        chunks = self.retrieval_service.expand_parent_chunks(state.get("chunks", []))
        return {
            **state,
            "chunks": chunks,
        }

    def _trim_context_node(self, state: ChatGraphState) -> ChatGraphState:
        """按上下文预算裁剪最终进入生成阶段的文本和图片。"""
        budgeted_context = trim_context_by_budget(
            settings=self.settings,
            chunks=state.get("chunks", []),
            images=state.get("images", []),
        )
        return {
            **state,
            "chunks": budgeted_context.chunks,
            "images": budgeted_context.images,
        }

    def _generate_node(self, state: ChatGraphState) -> ChatGraphState:
        """基于最终上下文生成回答。"""
        session_context = state.get("session_context")
        answer_result = self.answer_service.generate_answer(
            question=state["question"],
            chunks=state.get("chunks", []),
            images=state.get("images", []),
            summary_text=session_context.summary_text if session_context else None,
            recent_messages=session_context.recent_messages if session_context else [],
        )
        return {
            **state,
            "answer_result": answer_result,
        }

    def _resolve_checkpoint_ref(self, session_id: str) -> str | None:
        """读取当前会话最近一次 LangGraph 检查点标识。"""
        checkpoint_tuple = get_graph_checkpointer().get_tuple(
            {
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": "chat",
                }
            }
        )
        if checkpoint_tuple is None:
            return None
        return checkpoint_tuple.config["configurable"].get("checkpoint_id")
