from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from loguru import logger


def ensure_legacy_cli_path() -> Path:
    """确保旧版 CLI Demo 目录可被当前根入口导入。"""
    legacy_dir = Path(__file__).resolve().parent / "legacy" / "cli_demo"
    if not legacy_dir.exists():
        raise FileNotFoundError(f"未找到旧版 CLI Demo 目录：{legacy_dir}")

    legacy_dir_str = str(legacy_dir)
    if legacy_dir_str not in sys.path:
        sys.path.insert(0, legacy_dir_str)
    return legacy_dir


def setup_logger() -> None:
    """配置旧版 CLI Demo 使用的简化日志格式。"""
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
    )


def build_parser() -> argparse.ArgumentParser:
    """构造迁移期根入口参数。"""
    parser = argparse.ArgumentParser(
        description="learning_rag 根入口。默认提示使用 FastAPI 后端；如需旧版 CLI Demo，请显式传 --legacy-cli。",
    )
    parser.add_argument(
        "--legacy-cli",
        action="store_true",
        help="进入旧版本地 CLI Demo，仅供迁移期参考。",
    )
    parser.add_argument(
        "--data-path",
        default="./data/",
        help="旧版 CLI Demo 读取的本地文档目录。",
    )
    parser.add_argument(
        "--preserve-legacy-data",
        action="store_true",
        help="运行旧版 CLI Demo 时保留已有的本地向量和分块产物。",
    )
    return parser


def initialization(path: str):
    """初始化旧版 CLI Demo 所需的本地文档和向量库。"""
    from chunker import SemanticChunker
    from config import get_config
    from file_loader import FileLoader
    from vector import VectorStoreManager

    config = get_config()
    loader = FileLoader()
    documents = loader.load(path)
    if not documents:
        raise ValueError(f"没得文档：{path}")

    logger.info("开始分块处理")
    chunker = SemanticChunker(
        config=config,
        breakpoint_threshold=0.6,
    )
    logger.info("chunker 配置好了，准备开始切分文档")
    chunks = chunker.split_documents(documents)
    logger.info("文档切分完成，共生成 {} 个块", len(chunks))
    logger.info("开始准备初始化向量数据库配置")
    vector = VectorStoreManager(config)
    vector.add_documents(chunks)
    return chunks, vector, config


def clear_history_data() -> None:
    """清理旧版 CLI Demo 的本地向量产物。"""
    shutil.rmtree("./data/chroma_db", ignore_errors=True)
    shutil.rmtree("./data/chunks", ignore_errors=True)


def run_legacy_cli(*, data_path: str, preserve_legacy_data: bool) -> int:
    """显式运行旧版 CLI Demo。"""
    ensure_legacy_cli_path()
    from multi_functional_chain import MutiFunctionalRAGChain
    from rag_graph import RAGGraph

    setup_logger()
    if not preserve_legacy_data:
        clear_history_data()

    chunks, vector, config = initialization(data_path)
    base_chain = MutiFunctionalRAGChain(
        documents=chunks,
        config=config,
        vector_store_manager=vector,
    )
    rag_chain = RAGGraph(base_chain)
    show_sources = False
    thread_id = "cli-session"

    while True:
        question = input("请输入您的问题: ").strip()
        if question.lower() in ["quit", "exit", "q"]:
            print("\n拜拜！")
            break

        if question.lower() == "sources":
            show_sources = not show_sources
            status = "开启" if show_sources else "关闭"
            print(f"\n来源显示已{status}\n")
            continue

        print("\n正在思考...\n")
        result = rag_chain.ask_interactive(question, thread_id=thread_id)
        if show_sources:
            print(f"回答:\n{result['answer']}\n")
            print("参考来源:")
            for index, source in enumerate(result["sources"], 1):
                print(f"  [{index}] {source['source']}")
                print(f"      {source['content'][:100]}...\n")
        else:
            print(f"回答:\n{result['answer']}\n")

    return 0


def print_fastapi_guidance() -> None:
    """输出当前推荐的主入口说明。"""
    print("当前仓库主入口已经切换为 FastAPI 后端。")
    print("推荐启动命令：")
    print("  uv run uvicorn app.main:app --reload")
    print("如果需要查看快速开始：")
    print("  specs/001-fastapi-rag-backend/quickstart.md")
    print("如果确实要进入旧版本地 CLI Demo，请显式执行：")
    print("  uv run python main.py --legacy-cli")
    print("旧版脚本已统一归档到：")
    print("  legacy/cli_demo/")


def main(argv: list[str] | None = None) -> int:
    """迁移期根入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.legacy_cli:
        print_fastapi_guidance()
        return 0

    return run_legacy_cli(
        data_path=args.data_path,
        preserve_legacy_data=args.preserve_legacy_data,
    )


if __name__ == "__main__":
    raise SystemExit(main())
