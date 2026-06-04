from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ContextBudget, RelatedImage, SourceItem, UsageInfo
from app.services.session_service import validate_session_id


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None
    message: str = Field(min_length=1)
    user_key: str | None = None
    include_sources: bool = True
    include_related_images: bool = True
    debug_context: bool = False

    @field_validator("session_id")
    @classmethod
    def validate_optional_session_id(cls, value: str | None) -> str | None:
        """当请求显式携带会话标识时，提前校验其格式。"""
        if value is None:
            return value
        return validate_session_id(value)


class ChatResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str = Field(min_length=1)

    @field_validator("session_id")
    @classmethod
    def validate_required_session_id(cls, value: str) -> str:
        """恢复会话时必须携带合法的会话标识。"""
        return validate_session_id(value)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    answer: str
    status: str
    resume_token: str | None = None
    sources: list[SourceItem]
    related_images: list[RelatedImage]
    context_budget: ContextBudget | None = None
    usage: UsageInfo | None = None


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: str
    summary: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_message_at: datetime | None = None
