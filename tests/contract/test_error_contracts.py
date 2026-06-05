from __future__ import annotations

from app.api.deps import AppError
from app.api.routes.chat import get_chat_service, get_session_service
from app.schemas.chat import ChatSessionResponse
from sqlalchemy.exc import OperationalError


class RateLimitedChatService:
    """模拟触发限流时的接口行为。"""

    def answer(self, *, request, session_id: str):
        raise AppError(
            error_code="rate_limited",
            message="请求过于频繁，请稍后再试。",
            status_code=429,
            details={"retry_after_seconds": 10, "scope": "chat"},
        )


class MissingSessionService:
    """模拟查询不存在会话时的统一错误响应。"""

    def get_session_response(self, *, session_id: str) -> ChatSessionResponse:
        raise AppError(
            error_code="not_found",
            message="找不到对应的会话。",
            status_code=404,
        )


class DatabaseUnavailableChatService:
    """模拟数据库连接不可用时的接口行为。"""

    def answer(self, *, request, session_id: str):
        raise OperationalError("SELECT 1", {}, Exception("connection timeout expired"))


def test_invalid_request_error_contract(client):
    """请求体校验失败时，应返回统一错误结构。"""
    response = client.post(
        "/api/v1/chat",
        json={"message": ""},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "invalid_request"
    assert payload["message"] == "请求参数校验失败。"
    assert isinstance(payload["details"]["errors"], list)


def test_not_found_error_contract(client):
    """查询不存在会话时，应返回统一的 not_found 结构。"""
    client.app.dependency_overrides[get_session_service] = lambda: MissingSessionService()
    try:
        response = client.get("/api/v1/chat/sessions/sess_missing_001")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 404
    payload = response.json()
    assert payload["error_code"] == "not_found"
    assert payload["message"] == "找不到对应的会话。"


def test_rate_limited_error_contract(client):
    """触发限流时，应返回前端可直接消费的 429 结构。"""
    client.app.dependency_overrides[get_chat_service] = lambda: RateLimitedChatService()
    try:
        response = client.post(
            "/api/v1/chat",
            json={"message": "高频测试"},
        )
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 429
    payload = response.json()
    assert payload["error_code"] == "rate_limited"
    assert payload["message"] == "请求过于频繁，请稍后再试。"
    assert payload["details"]["retry_after_seconds"] == 10


def test_database_unavailable_error_contract(client):
    """数据库不可用时，应返回前端可识别的 503 结构。"""
    client.app.dependency_overrides[get_chat_service] = lambda: DatabaseUnavailableChatService()
    try:
        response = client.post(
            "/api/v1/chat",
            json={"message": "数据库连接测试"},
        )
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 503
    payload = response.json()
    assert payload["error_code"] == "database_unavailable"
    assert payload["message"] == "数据库暂时不可用，请确认 PostgreSQL 已启动且 DATABASE_URL 配置正确。"
    assert payload["details"]["exception_type"] == "OperationalError"
