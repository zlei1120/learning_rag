from __future__ import annotations

import re


def test_chat_generates_session_id_when_missing(client):
    """未提供会话标识时，接口应自动生成新的 session_id。"""
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "帮我总结一下这篇文章。",
            "debug_context": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert re.fullmatch(r"sess_[0-9a-f]{32}", payload["session_id"])
    assert payload["status"] == "completed"
    assert payload["context_budget"]["max_input_tokens"] == 24000


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
