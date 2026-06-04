from __future__ import annotations

from datetime import datetime, timezone

from app.api.deps import AppError
from app.api.routes.chat import get_session_service
from app.schemas.chat import ChatSessionResponse


class StubSessionService:
    """为会话接口合同测试提供可控替身。"""

    def get_session_response(self, *, session_id: str) -> ChatSessionResponse:
        if session_id == "sess_missing_001":
            raise AppError(
                error_code="not_found",
                message="找不到对应的会话。",
                status_code=404,
            )

        return ChatSessionResponse(
            session_id=session_id,
            status="active",
            summary="用户先问了数据库配置，再追问了端口含义。",
            created_at=datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 4, 8, 5, tzinfo=timezone.utc),
            last_message_at=datetime(2026, 6, 4, 8, 5, tzinfo=timezone.utc),
        )


def test_chat_session_endpoint_returns_session_metadata(client):
    """会话查询接口应返回会话状态和摘要信息。"""
    client.app.dependency_overrides[get_session_service] = lambda: StubSessionService()
    try:
        response = client.get("/api/v1/chat/sessions/sess_demo_001")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "sess_demo_001"
    assert payload["status"] == "active"
    assert "数据库配置" in payload["summary"]
    assert payload["last_message_at"].startswith("2026-06-04T08:05:00")


def test_chat_session_endpoint_returns_not_found_error(client):
    """查询不存在会话时应返回统一错误结构。"""
    client.app.dependency_overrides[get_session_service] = lambda: StubSessionService()
    try:
        response = client.get("/api/v1/chat/sessions/sess_missing_001")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 404
    payload = response.json()
    assert payload["error_code"] == "not_found"
    assert payload["message"] == "找不到对应的会话。"
