from __future__ import annotations

from app.api.routes.chat import get_chat_service
from app.schemas.chat import ChatResponse
from app.schemas.common import ContextBudget, RelatedImage, SourceItem, UsageInfo


class StubStreamingChatService:
    """为流式接口合同测试提供稳定输出。"""

    def answer(self, *, request, session_id: str) -> ChatResponse:
        return ChatResponse(
            session_id=session_id,
            answer="这里的端口指 PostgreSQL 对外监听的 5432 端口。",
            status="completed",
            sources=[
                SourceItem(
                    source_type="post_chunk",
                    label="数据库教程",
                    slug="db-guide",
                    title_path="数据库教程 > 准备数据库",
                    content_excerpt="先确认 PostgreSQL 服务已经启动，再检查 5432 端口。",
                )
            ],
            related_images=[
                RelatedImage(
                    url="/uploads/tutorial/db-step.png",
                    alt_text="数据库配置截图",
                    caption="截图展示了端口和账号权限。",
                    source_slug="db-guide",
                    title_path="数据库教程 > 准备数据库",
                )
            ],
            context_budget=ContextBudget(max_input_tokens=24000, retrieved_chunks_tokens=12000),
            usage=UsageInfo(prompt_tokens=120, completion_tokens=32, total_tokens=152),
        )


def test_chat_stream_returns_sse_events(client):
    """流式问答接口应返回可解析的 SSE 事件流。"""
    client.app.dependency_overrides[get_chat_service] = lambda: StubStreamingChatService()
    try:
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "这里的端口是什么意思？",
                "debug_context": True,
            },
        )
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    payload = response.text
    assert "event: message.delta" in payload
    assert "event: source" in payload
    assert "event: related_image" in payload
    assert "event: context_budget" in payload
    assert "event: usage" in payload
    assert "event: message.completed" in payload
    assert "5432" in payload
