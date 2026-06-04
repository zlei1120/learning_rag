from __future__ import annotations

from app.core.config import get_settings, reset_settings_cache
from app.main import create_app


def test_create_app_reads_runtime_config(monkeypatch):
    """启动应用时应读取环境变量并反映到基础响应中。"""
    monkeypatch.setenv("APP_NAME", "rag-backend-test")
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    monkeypatch.setenv("DEBUG", "true")
    reset_settings_cache()

    app = create_app()

    assert app.title == "rag-backend-test"
    assert app.version == "9.9.9"
    assert app.debug is True


def test_health_endpoint_survives_database_unavailable(client, monkeypatch):
    """数据库不可用时，健康检查应返回降级状态而不是直接报错。"""
    monkeypatch.setattr("app.api.routes.health.check_database_health", lambda: "unavailable")

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"] == "unavailable"
    assert payload["graph_runtime"] == "langgraph:ready"


def test_create_app_uses_default_bailian_base_url_when_env_blank(monkeypatch):
    """兼容地址配置为空时，启动过程应回退到百炼默认地址。"""
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    reset_settings_cache()

    app = create_app()
    settings = get_settings()

    assert app is not None
    assert settings.openai_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
