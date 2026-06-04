from __future__ import annotations

import importlib.util
import sys
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
    assert "legacy/cli_demo/" in captured.out


def test_ensure_legacy_cli_path_prepends_legacy_directory(monkeypatch):
    """旧版 CLI 目录应被插入到导入搜索路径最前面，且避免重复插入。"""
    module = load_root_main_module()
    legacy_dir = Path(__file__).resolve().parents[2] / "legacy" / "cli_demo"

    filtered_path = [
        item
        for item in sys.path
        if Path(item or ".").resolve() != legacy_dir.resolve()
    ]
    monkeypatch.setattr(sys, "path", filtered_path)

    inserted_dir = module.ensure_legacy_cli_path()
    assert inserted_dir == legacy_dir
    assert Path(sys.path[0]).resolve() == legacy_dir.resolve()

    module.ensure_legacy_cli_path()
    legacy_count = sum(
        1
        for item in sys.path
        if Path(item or ".").resolve() == legacy_dir.resolve()
    )
    assert legacy_count == 1
