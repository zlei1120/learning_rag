# legacy

这里存放迁移期保留的旧版脚本，避免继续和当前 FastAPI 主线混在根目录。

## 当前目录

- `cli_demo/`
  原先根目录下的本地 CLI RAG Demo、评估脚本和实验性模块

## 使用说明

- 推荐主入口仍然是 FastAPI：
  `uv run uvicorn app.main:app --reload`
- 如果需要进入旧版本地 CLI Demo：
  `uv run python main.py --legacy-cli`
- 如果需要单独运行旧评估脚本：
  `uv run python legacy/cli_demo/eval_rag.py`

## 注意事项

- 这里的脚本仅用于历史参考、迁移过渡和局部验证。
- 新功能默认不要继续加在这里，优先落到 `app/`、`scripts/` 或正式文档目录。
