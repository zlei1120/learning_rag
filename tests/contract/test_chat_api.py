from __future__ import annotations

import re

from app.api.routes.chat import get_chat_service
from app.schemas.chat import ChatResponse
from app.schemas.common import ContextBudget, RelatedImage, SourceItem, UsageInfo


class StubChatService:
    """为合同测试提供可控的问答服务替身。"""

    def answer(self, *, request, session_id: str) -> ChatResponse:
        return ChatResponse(
            session_id=session_id,
            answer="这是基于已同步博客内容生成的测试回答。",
            status="completed",
            sources=[
                SourceItem(
                    source_type="post_chunk",
                    label="数据库教程",
                    slug="db-guide",
                    title_path="数据库教程 > 准备数据库",
                    content_excerpt="先打开数据库管理页面，确认 PostgreSQL 服务已经启动。",
                )
            ]
            if request.include_sources
            else [],
            related_images=[
                RelatedImage(
                    url="/uploads/tutorial/db-step.png",
                    alt_text="数据库配置截图",
                    caption="数据库配置截图展示端口和账号权限检查。",
                    source_slug="db-guide",
                    title_path="数据库教程 > 准备数据库",
                )
            ]
            if request.include_related_images
            else [],
            context_budget=ContextBudget(max_input_tokens=24000) if request.debug_context else None,
            usage=UsageInfo(),
        )


def test_chat_generates_session_id_when_missing(client):
    """未提供会话标识时，接口应自动生成新的 session_id。"""
    client.app.dependency_overrides[get_chat_service] = lambda: StubChatService()
    try:
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "帮我总结一下这篇文章。",
                "debug_context": True,
            },
        )
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert re.fullmatch(r"sess_[0-9a-f]{32}", payload["session_id"])
    assert payload["status"] == "completed"
    assert payload["context_budget"]["max_input_tokens"] == 24000
    assert payload["sources"][0]["slug"] == "db-guide"
    assert payload["related_images"][0]["url"] == "/uploads/tutorial/db-step.png"


def test_chat_rejects_invalid_session_id_in_body(client):
    """请求体中的非法 session_id 应按统一错误结构返回。"""
    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "bad id",
            "message": "测试一下。",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "invalid_request"
    assert payload["message"] == "请求参数校验失败。"


def test_chat_session_endpoint_rejects_invalid_path_session_id(client):
    """路径参数中的非法 session_id 也应返回业务级 400。"""
    response = client.get("/api/v1/chat/sessions/bad id")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "invalid_request"
    assert "session_id 格式非法" in payload["message"]
