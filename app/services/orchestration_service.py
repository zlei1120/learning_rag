from __future__ import annotations

from dataclasses import dataclass


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
