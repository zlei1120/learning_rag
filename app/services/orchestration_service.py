from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver


@dataclass(slots=True)
class OrchestrationRuntime:
    """为后续 LangGraph 编排运行时预留的封装对象。"""

    provider: str = "langgraph"
    status: str = "ready"

    def to_health_label(self) -> str:
        """返回适合健康检查输出的运行时摘要。"""
        return f"{self.provider}:{self.status}"


def get_orchestration_runtime() -> OrchestrationRuntime:
    return OrchestrationRuntime()


@lru_cache(maxsize=1)
def get_graph_checkpointer() -> BaseCheckpointSaver:
    """返回进程级共享的 LangGraph 检查点保存器。"""
    return InMemorySaver().with_allowlist(
        [
            ("app.services.answer_service", "AnswerResult"),
            ("app.services.retrieval_service", "RetrievedChunk"),
            ("app.services.retrieval_service", "RetrievedImage"),
            ("app.services.retrieval_service", "RetrievalResult"),
            ("app.services.session_service", "ConversationMessage"),
            ("app.services.session_service", "SessionContext"),
        ]
    )


def reset_graph_checkpointer() -> None:
    """清空图检查点缓存，避免测试之间串状态。"""
    get_graph_checkpointer.cache_clear()
