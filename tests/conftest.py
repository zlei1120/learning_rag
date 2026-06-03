from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import reset_settings_cache
from app.core.database import reset_database_cache
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_runtime_caches() -> None:
    """每个测试前重置配置和数据库缓存，避免环境状态串扰。"""
    reset_settings_cache()
    reset_database_cache()


@pytest.fixture()
def client() -> TestClient:
    """提供 FastAPI 测试客户端。"""
    app = create_app()
    return TestClient(app)
