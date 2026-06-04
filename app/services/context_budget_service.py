from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.schemas.common import ContextBudget

if TYPE_CHECKING:
    from app.services.retrieval_service import RetrievedChunk, RetrievedImage


def build_default_context_budget(settings: Settings) -> ContextBudget:
    return ContextBudget(
        max_input_tokens=settings.chat_context_max_tokens,
        recent_messages_tokens=settings.chat_context_recent_messages_tokens,
        summary_memory_tokens=settings.chat_context_summary_tokens,
        retrieved_chunks_tokens=settings.chat_context_retrieval_tokens,
        image_feature_tokens=settings.chat_context_image_tokens,
        reserved_output_tokens=settings.chat_context_reserved_output_tokens,
    )


@dataclass(slots=True)
class BudgetedContext:
    """预算裁剪后的问答上下文。"""

    chunks: list["RetrievedChunk"]
    images: list["RetrievedImage"]


def trim_context_by_budget(
    *,
    settings: Settings,
    chunks: list["RetrievedChunk"],
    images: list["RetrievedImage"],
) -> BudgetedContext:
    """按文本和图片各自预算裁剪上下文。"""
    trimmed_chunks = _trim_items_by_budget(
        items=chunks,
        budget_tokens=settings.chat_context_retrieval_tokens,
        fallback_token_cost=220,
    )
    trimmed_images = _trim_items_by_budget(
        items=images,
        budget_tokens=settings.chat_context_image_tokens,
        fallback_token_cost=160,
    )
    return BudgetedContext(chunks=trimmed_chunks, images=trimmed_images)


def _trim_items_by_budget(*, items: list[object], budget_tokens: int, fallback_token_cost: int) -> list[object]:
    """按 token 预算顺序保留项目。"""
    selected_items: list[object] = []
    used_tokens = 0

    for item in items:
        token_estimate = getattr(item, "token_estimate", None)
        token_cost = token_estimate if isinstance(token_estimate, int) and token_estimate > 0 else fallback_token_cost
        if selected_items and used_tokens + token_cost > budget_tokens:
            continue
        if not selected_items and token_cost > budget_tokens:
            selected_items.append(item)
            break

        selected_items.append(item)
        used_tokens += token_cost

    return selected_items
