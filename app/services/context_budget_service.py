from __future__ import annotations

from app.core.config import Settings
from app.schemas.common import ContextBudget


def build_default_context_budget(settings: Settings) -> ContextBudget:
    return ContextBudget(
        max_input_tokens=settings.chat_context_max_tokens,
        recent_messages_tokens=settings.chat_context_recent_messages_tokens,
        summary_memory_tokens=settings.chat_context_summary_tokens,
        retrieved_chunks_tokens=settings.chat_context_retrieval_tokens,
        image_feature_tokens=settings.chat_context_image_tokens,
        reserved_output_tokens=settings.chat_context_reserved_output_tokens,
    )
