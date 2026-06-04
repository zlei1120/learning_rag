from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.api.deps import AppError
from app.core.config import Settings
from app.services.memory_service import MemoryService
from app.services.session_service import SessionService


@dataclass
class FakeChatSession:
    """会话线程替身。"""

    id: str
    session_id: str
    user_key: str | None = None
    session_scope: str = "anonymous"
    status: str = "active"
    summary_text: str | None = None
    last_message_at: datetime | None = None
    last_checkpoint_ref: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc))


@dataclass
class FakeChatMessage:
    """消息记录替身。"""

    id: str
    chat_session_id: str
    message_index: int
    role: str
    content: str
    content_summary: str | None = None
    source_payload_json: dict[str, object] | None = None
    budget_included: bool = False
    trimmed: bool = False
    token_estimate: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc))


@dataclass
class FakeMemoryRecord:
    """摘要记忆替身。"""

    chat_session_id: str
    user_key: str | None
    content: str
    content_hash: str
    memory_scope: str = "session"
    memory_type: str = "summary"
    importance_score: float | None = 0.8
    created_at: datetime = field(default_factory=lambda: datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc))


class FakeChatSessionRepository:
    """内存版会话仓储。"""

    def __init__(self) -> None:
        self.by_public_id: dict[str, FakeChatSession] = {}
        self.by_row_id: dict[str, FakeChatSession] = {}

    def get_by_id(self, session_row_id: str) -> FakeChatSession | None:
        return self.by_row_id.get(session_row_id)

    def get_by_public_session_id(self, session_id: str) -> FakeChatSession | None:
        return self.by_public_id.get(session_id)

    def get_or_create(self, *, session_id: str, user_key: str | None = None) -> FakeChatSession:
        chat_session = self.by_public_id.get(session_id)
        if chat_session is None:
            chat_session = FakeChatSession(
                id=f"row-{session_id}",
                session_id=session_id,
                user_key=user_key,
                session_scope="user" if user_key else "anonymous",
            )
            self.by_public_id[session_id] = chat_session
            self.by_row_id[chat_session.id] = chat_session
            return chat_session

        if user_key:
            chat_session.user_key = user_key
            chat_session.session_scope = "user"
        return chat_session

    def touch(self, chat_session: FakeChatSession, *, checkpoint_ref: str | None = None) -> FakeChatSession:
        chat_session.last_message_at = datetime(2026, 6, 4, 8, 5, tzinfo=timezone.utc)
        chat_session.updated_at = datetime(2026, 6, 4, 8, 5, tzinfo=timezone.utc)
        chat_session.last_checkpoint_ref = checkpoint_ref
        return chat_session

    def update_summary(self, chat_session: FakeChatSession, summary_text: str | None) -> FakeChatSession:
        chat_session.summary_text = summary_text
        return chat_session


class FakeChatMessageRepository:
    """内存版消息仓储。"""

    def __init__(self) -> None:
        self.messages_by_session: dict[str, list[FakeChatMessage]] = {}

    def list_all(self, chat_session_id: str) -> list[FakeChatMessage]:
        return list(self.messages_by_session.get(chat_session_id, []))

    def list_recent(self, chat_session_id: str, *, limit: int) -> list[FakeChatMessage]:
        return list(self.messages_by_session.get(chat_session_id, [])[-limit:])

    def get_next_message_index(self, chat_session_id: str) -> int:
        return len(self.messages_by_session.get(chat_session_id, [])) + 1

    def create_message(
        self,
        *,
        chat_session_id: str,
        message_index: int,
        role: str,
        content: str,
        content_summary: str | None = None,
        source_payload_json: dict[str, object] | None = None,
        budget_included: bool = False,
        trimmed: bool = False,
        token_estimate: int | None = None,
    ) -> FakeChatMessage:
        message = FakeChatMessage(
            id=f"{chat_session_id}-{message_index}",
            chat_session_id=chat_session_id,
            message_index=message_index,
            role=role,
            content=content,
            content_summary=content_summary,
            source_payload_json=source_payload_json,
            budget_included=budget_included,
            trimmed=trimmed,
            token_estimate=token_estimate,
        )
        self.messages_by_session.setdefault(chat_session_id, []).append(message)
        return message

    def mark_context_window(self, *, chat_session_id: str, included_message_ids: list[str]) -> None:
        included_ids = set(included_message_ids)
        for message in self.messages_by_session.get(chat_session_id, []):
            message.budget_included = message.id in included_ids
            message.trimmed = message.id not in included_ids


class FakeMemoryRepository:
    """内存版摘要记忆仓储。"""

    def __init__(self) -> None:
        self.records_by_session: dict[str, FakeMemoryRecord] = {}

    def get_latest_session_summary(self, chat_session_id: str) -> FakeMemoryRecord | None:
        return self.records_by_session.get(chat_session_id)

    def upsert_session_summary(
        self,
        *,
        chat_session_id: str,
        user_key: str | None,
        content: str,
        content_hash: str,
        importance_score: float | None = 0.8,
    ) -> FakeMemoryRecord:
        record = FakeMemoryRecord(
            chat_session_id=chat_session_id,
            user_key=user_key,
            content=content,
            content_hash=content_hash,
            importance_score=importance_score,
        )
        self.records_by_session[chat_session_id] = record
        return record

    def delete_session_summary(self, chat_session_id: str) -> None:
        self.records_by_session.pop(chat_session_id, None)


def test_session_service_records_messages_and_keeps_sessions_isolated():
    """不同 session_id 的消息不能混在一起。"""
    chat_session_repository = FakeChatSessionRepository()
    chat_message_repository = FakeChatMessageRepository()
    memory_repository = FakeMemoryRepository()
    service = SessionService(
        session=object(),
        settings=Settings(chat_context_recent_messages_tokens=200, chat_history_message_limit=6),
        chat_session_repository=chat_session_repository,
        chat_message_repository=chat_message_repository,
        memory_repository=memory_repository,
    )

    service.record_exchange(
        session_id="sess_alpha_001",
        user_key=None,
        user_message="第一轮问题",
        assistant_message="第一轮回答",
    )
    service.record_exchange(
        session_id="sess_alpha_001",
        user_key=None,
        user_message="第二轮问题",
        assistant_message="第二轮回答",
    )
    service.record_exchange(
        session_id="sess_beta_001",
        user_key=None,
        user_message="另一个会话的问题",
        assistant_message="另一个会话的回答",
    )

    alpha_context = service.get_or_create_context(session_id="sess_alpha_001")
    beta_context = service.get_or_create_context(session_id="sess_beta_001")

    assert [message.content for message in alpha_context.recent_messages] == [
        "第一轮问题",
        "第一轮回答",
        "第二轮问题",
        "第二轮回答",
    ]
    assert [message.content for message in beta_context.recent_messages] == [
        "另一个会话的问题",
        "另一个会话的回答",
    ]


def test_memory_service_summarizes_older_messages():
    """超过最近消息窗口后，应把较早对话压缩成摘要记忆。"""
    chat_session_repository = FakeChatSessionRepository()
    chat_message_repository = FakeChatMessageRepository()
    memory_repository = FakeMemoryRepository()
    session_service = SessionService(
        session=object(),
        settings=Settings(chat_context_recent_messages_tokens=500, chat_history_message_limit=4, chat_summary_max_chars=160),
        chat_session_repository=chat_session_repository,
        chat_message_repository=chat_message_repository,
        memory_repository=memory_repository,
    )
    memory_service = MemoryService(
        session=object(),
        settings=Settings(chat_history_message_limit=4, chat_summary_max_chars=160),
        chat_message_repository=chat_message_repository,
        chat_session_repository=chat_session_repository,
        memory_repository=memory_repository,
    )

    for index in range(3):
        session_service.record_exchange(
            session_id="sess_summary_001",
            user_key=None,
            user_message=f"用户第 {index + 1} 轮提问",
            assistant_message=f"助手第 {index + 1} 轮回答",
        )

    context = session_service.get_or_create_context(session_id="sess_summary_001")
    summary_text = memory_service.refresh_session_summary(context)

    assert summary_text is not None
    assert "用户第 1 轮提问" in summary_text
    assert memory_repository.get_latest_session_summary("row-sess_summary_001") is not None
    session_response = session_service.get_session_response(session_id="sess_summary_001")
    assert session_response.summary == summary_text


def test_session_service_get_session_response_raises_not_found():
    """查询不存在会话时应抛出统一业务异常。"""
    service = SessionService(
        session=object(),
        settings=Settings(),
        chat_session_repository=FakeChatSessionRepository(),
        chat_message_repository=FakeChatMessageRepository(),
        memory_repository=FakeMemoryRepository(),
    )

    with pytest.raises(AppError, match="找不到对应的会话。"):
        service.get_session_response(session_id="sess_missing_001")
