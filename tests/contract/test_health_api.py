from __future__ import annotations


def test_health_returns_runtime_status(client, monkeypatch):
    """健康检查应返回服务、数据库和图运行时状态。"""
    monkeypatch.setattr("app.api.routes.health.check_database_health", lambda: "ok")

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "learning-rag-api"
    assert payload["version"] == "0.1.0"
    assert payload["database"] == "ok"
    assert payload["graph_runtime"] == "langgraph:ready"


def test_health_reports_degraded_when_database_unavailable(client, monkeypatch):
    """数据库不可用时，健康检查应降级但仍返回可解释状态。"""
    monkeypatch.setattr("app.api.routes.health.check_database_health", lambda: "unavailable")

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"] == "unavailable"
