from __future__ import annotations

import importlib.util
from pathlib import Path


def load_root_main_module():
    """按文件路径加载根目录 `main.py`。"""
    module_path = Path(__file__).resolve().parents[2] / "main.py"
    spec = importlib.util.spec_from_file_location("learning_rag_root_main", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_main_prints_fastapi_guidance_when_no_legacy_flag(capsys):
    """根入口默认应提示使用 FastAPI，而不是直接进入旧版 CLI。"""
    module = load_root_main_module()

    exit_code = module.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "FastAPI 后端" in captured.out
    assert "uv run uvicorn app.main:app --reload" in captured.out
