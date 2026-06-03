from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    details: dict[str, object] | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    version: str | None = None
    database: str | None = None
    graph_runtime: str | None = None


class ContextBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_input_tokens: int | None = None
    recent_messages_tokens: int | None = None
    summary_memory_tokens: int | None = None
    retrieved_chunks_tokens: int | None = None
    image_feature_tokens: int | None = None
    reserved_output_tokens: int | None = None


class UsageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class SourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    label: str
    slug: str | None = None
    title_path: str | None = None
    content_excerpt: str | None = None


class RelatedImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    alt_text: str | None = None
    caption: str | None = None
    source_slug: str | None = None
    title_path: str | None = None
